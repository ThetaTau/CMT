import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.models import BigLittle, PendingPairing
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

NAMES = "little_full_name,big_full_name\n"


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


def _member(chapter, name, status="active", **kwargs):
    """A member whose every name field is predictable, so fuzzy matches are too."""
    first, _, last = name.partition(" ")
    kwargs.setdefault("middle_name", "")
    kwargs.setdefault("nickname", "")
    return UserFactory(chapter=chapter, name=name, first_name=first, last_name=last, current_status=status, **kwargs)


def _import(chapter, text, actor=None):
    return services.import_big_little_csv(text.encode(), chapter, actor)


def _outcomes(result):
    return [(row.line, row.outcome, row.message) for row in result.rows]


# ---------------------------------------------------------------------------
# Importing names
# ---------------------------------------------------------------------------
def test_exact_names_are_recorded_whatever_the_capitals_order_and_punctuation(chapter):
    big = _member(chapter, "John Smith")
    little = _member(chapter, "Mary Lee")
    twin = _member(chapter, "José Ortiz")

    result = _import(chapter, NAMES + 'MARY LEE,john smith\n"Ortiz, Jose",Smith John Jr.\n')

    assert _outcomes(result) == [(2, "created", "Recorded"), (3, "created", "Recorded")]
    assert services.current_big(little) == big
    assert services.current_big(twin) == big
    assert not PendingPairing.objects.exists()


@pytest.mark.parametrize(
    "header, row",
    [
        ("Little Full Name,Big Full Name", "Mary Lee,John Smith"),
        ("big_name,little_name", "John Smith,Mary Lee"),
        ("badge_number_big,little_full_name", "{badge},Mary Lee"),
        # A badge number wins over the name when a row has both.
        ("badge_number_big,big_full_name,little_full_name", "{badge},Somebody Else,Mary Lee"),
    ],
)
def test_names_and_badge_numbers_can_be_mixed(chapter, header, row):
    big = _member(chapter, "John Smith")
    little = _member(chapter, "Mary Lee")

    result = _import(chapter, f"{header}\n{row.format(badge=big.badge_number)}\n")

    assert _outcomes(result) == [(2, "created", "Recorded")]
    assert services.current_big(little) == big


def test_a_missing_name_and_a_not_initiated_member_are_errors(chapter):
    _member(chapter, "John Smith")
    _member(chapter, "Pat Pnm", status="pnm")

    result = _import(chapter, NAMES + "Pat Pnm,John Smith\n,John Smith\n")

    assert _outcomes(result) == [
        (2, "error", "Pat Pnm is not initiated, so they cannot have a Big yet."),
        (3, "error", "The Little name is missing."),
    ]
    assert not PendingPairing.objects.exists()


def test_a_misspelled_name_waits_for_review_with_suggestions(chapter):
    officer = _member(chapter, "Olive Officer")
    big = _member(chapter, "John Smith")
    little = _member(chapter, "Mary Lee")

    result = _import(chapter, NAMES + "Mary Lee,Jon Smith\n", actor=officer)

    assert _outcomes(result) == [
        (2, "review", 'No member of alpha is named exactly "Jon Smith". Choose the member on the review page.')
    ]
    assert result.review_count == 1
    assert "1 waiting for review" in result.summary
    assert not BigLittle.objects.exists()
    item = PendingPairing.objects.get()
    assert (item.chapter, item.line, item.little_text, item.big_text) == (chapter, 2, "Mary Lee", "Jon Smith")
    assert (item.little, item.big, item.uploaded_by, item.status) == (little, None, officer, "pending")
    assert item.little_suggestions == []
    assert item.big_suggestions[0] == {"pk": big.pk, "score": 0.95}


def test_names_shared_by_two_members_and_unknown_names_wait_for_review(chapter):
    _member(chapter, "John Smith")
    _member(chapter, "John Smith")

    result = _import(chapter, NAMES + "Zed Quux,John Smith\n")

    assert _outcomes(result) == [
        (
            2,
            "review",
            'More than one member of alpha is named "John Smith". No member of alpha is named exactly "Zed Quux". '
            "Choose the members on the review page.",
        )
    ]
    item = PendingPairing.objects.get()
    assert item.little_suggestions == []
    assert [suggestion["score"] for suggestion in item.big_suggestions] == [1.0, 1.0]


def test_a_row_with_a_problem_on_its_found_side_is_not_sent_for_review(chapter):
    _member(chapter, "Pat Pnm", status="pnm")

    result = _import(chapter, NAMES + "Zed Quux,Pat Pnm\n")

    assert _outcomes(result) == [(2, "error", "Pat Pnm is not initiated, so they cannot be a Big.")]
    assert not PendingPairing.objects.exists()


def test_uploading_again_updates_the_waiting_row_instead_of_adding_one(chapter):
    _member(chapter, "Mary Lee")
    _import(chapter, NAMES + "Mary Lee,Jon Smith\n")

    again = _import(chapter, NAMES + "Someone Else,John Doe\nmary lee,JON SMITH\n")

    assert [row.outcome for row in again.rows] == ["review", "review"]
    assert PendingPairing.objects.count() == 2
    assert PendingPairing.objects.get(little_text="mary lee").line == 3


def test_uploading_again_skips_dismissed_rows_and_reuses_saved_answers(chapter):
    officer = _member(chapter, "Olive Officer")
    big = _member(chapter, "John Smith")
    little = _member(chapter, "Mary Lee")
    text = NAMES + "Mary Lee,Jon Smith\nZed Quux,John Smith\n"
    _import(chapter, text)
    saved, dismissed = PendingPairing.objects.order_by("line")
    services.save_pending(saved, little, big, officer)
    services.dismiss_pending(dismissed, officer)

    again = _import(chapter, text)

    assert _outcomes(again) == [
        (2, "unchanged", "No change, using the members picked on the review page"),
        (3, "skipped", "Skipped: this row was dismissed on the review page."),
    ]
    assert "1 skipped" in again.summary
    assert BigLittle.objects.count() == 1


def test_a_saved_answer_whose_member_was_deleted_goes_back_for_review(chapter):
    big = _member(chapter, "John Smith")
    little = _member(chapter, "Mary Lee")
    _import(chapter, NAMES + "Mary Lee,Jon Smith\n")
    services.save_pending(PendingPairing.objects.get(), little, big, None)
    little.delete()

    again = _import(chapter, NAMES + "Mary Lee,Jon Smith\n")

    assert [row.outcome for row in again.rows] == ["review"]
    assert PendingPairing.objects.get().status == PendingPairing.Status.PENDING


# ---------------------------------------------------------------------------
# The review page
# ---------------------------------------------------------------------------
@pytest.fixture
def officer(chapter):
    officer = _member(chapter, "Olive Officer")
    officer.groups.add(Group.objects.get_or_create(name="officer")[0])
    return officer


@pytest.fixture
def officer_client(auto_login_user, officer):
    client, _ = auto_login_user(user=officer)
    return client


@pytest.fixture
def waiting(chapter, officer):
    """One row whose Little matched and whose Big is misspelled."""
    big = _member(chapter, "John Smith")
    little = _member(chapter, "Mary Lee")
    _import(chapter, NAMES + "Mary Lee,Jon Smith\n", actor=officer)
    return PendingPairing.objects.get(), little, big


def _post(client, item, **data):
    payload = {"item": item.pk, "action": "save"}
    payload.update({f"row-{item.pk}-{key}": value for key, value in data.items()})
    return client.post(reverse("biglittle:review"), payload)


def _messages(response):
    return [str(message) for message in response.wsgi_request._messages]


def test_the_page_lists_waiting_rows_with_the_found_member_and_suggestions(officer_client, chapter, waiting):
    item, little, big = waiting
    other = ChapterFactory(name="beta")
    PendingPairing.objects.create(chapter=other, fingerprint="x", little_text="Not Mine")
    PendingPairing.objects.create(
        chapter=chapter, fingerprint="y", little_text="Done Already", status=PendingPairing.Status.DISMISSED
    )

    response = officer_client.get(reverse("biglittle:review"))

    assert response.status_code == 200
    rows = response.context["rows"]
    assert [row_item for row_item, _ in rows] == [item]
    form = rows[0][1]
    assert form.fields["little"].choices == [(little.pk, f"Mary Lee (#{little.badge_number}), matched in the file")]
    assert form.fields["big"].choices[0] == (big.pk, f"John Smith (#{big.badge_number}), 95% match")
    assert form.initial == {"little": little.pk, "big": big.pk}
    content = response.content.decode()
    assert 'Big in the file: "Jon Smith"' in content
    assert "Not Mine" not in content


def test_each_choice_links_to_the_members_profile_in_a_new_tab(officer_client, waiting):
    _, little, big = waiting

    content = officer_client.get(reverse("biglittle:review")).content.decode()

    for member in (little, big):
        assert f'href="{reverse("biglittle:member", args=[member.pk])}" target="_blank" rel="noopener"' in content


def test_saving_a_suggestion_records_the_pairing_and_closes_the_row(officer_client, officer, waiting):
    item, little, big = waiting

    response = _post(officer_client, item, little=little.pk, big=big.pk)

    assert response.url == reverse("biglittle:review")
    assert services.current_big(little) == big
    assert BigLittle.objects.get().source == BigLittle.Source.UPLOAD
    item.refresh_from_db()
    assert (item.status, item.little, item.big, item.resolved_by) == ("saved", little, big, officer)
    assert item.resolved_at is not None
    assert _messages(response)[-1] == "Recorded John Smith as Mary Lee's Big."


def test_a_searched_member_is_used_instead_of_the_suggestion(officer_client, chapter, waiting):
    item, little, big = waiting
    someone = _member(chapter, "Sam Searched")

    _post(officer_client, item, little=little.pk, big=big.pk, big_other=someone.pk)

    assert services.current_big(little) == someone


def test_a_side_with_nothing_chosen_shows_an_error(officer_client, waiting):
    item, little, _ = waiting

    response = _post(officer_client, item, little=little.pk)

    assert response.status_code == 200
    form = response.context["rows"][0][1]
    assert form.errors["big_other"] == ["Choose the Big, or dismiss this row."]
    assert not BigLittle.objects.exists()


def test_the_rules_still_apply_on_review(officer_client, waiting):
    item, little, _ = waiting

    response = _post(officer_client, item, little=little.pk, big_other=little.pk)

    assert response.context["rows"][0][1].non_field_errors() == ["A member cannot be their own Big."]
    assert not BigLittle.objects.exists()


def test_a_choice_that_was_not_offered_is_refused(officer_client, chapter, waiting):
    item, little, _ = waiting
    stranger = _member(chapter, "Not Suggested")

    response = _post(officer_client, item, little=little.pk, big=stranger.pk)

    assert "big" in response.context["rows"][0][1].errors
    assert not BigLittle.objects.exists()


def test_dismissing_closes_the_row_without_saving(officer_client, officer, waiting):
    item, _, _ = waiting

    response = officer_client.post(reverse("biglittle:review"), {"item": item.pk, "action": "dismiss"})

    item.refresh_from_db()
    assert (item.status, item.resolved_by) == ("dismissed", officer)
    assert not BigLittle.objects.exists()
    assert _messages(response)[-1] == 'Dismissed line 2: Little "Mary Lee", Big "Jon Smith".'


@pytest.mark.parametrize("which", ["closed", "other chapter", "not a number"])
def test_rows_that_are_not_waiting_cannot_be_changed(officer_client, officer, waiting, which):
    item, little, big = waiting
    if which == "closed":
        services.dismiss_pending(item, officer)
        target = item.pk
    elif which == "other chapter":
        PendingPairing.objects.filter(pk=item.pk).update(chapter=ChapterFactory(name="beta"))
        target = item.pk
    else:
        target = "abc"

    response = officer_client.post(
        reverse("biglittle:review"),
        {"item": target, "action": "save", f"row-{item.pk}-little": little.pk, f"row-{item.pk}-big": big.pk},
    )

    assert response.url == reverse("biglittle:review")
    assert _messages(response)[-1] == "That row is no longer waiting for review."
    assert not BigLittle.objects.exists()


def test_a_plain_member_is_turned_away(auto_login_user, chapter, waiting):
    item, _, _ = waiting
    client, _ = auto_login_user(user=_member(chapter, "Plain Member"))

    assert client.get(reverse("biglittle:review")).url == reverse("biglittle:list")
    assert client.post(reverse("biglittle:review"), {"item": item.pk, "action": "dismiss"}).url == reverse(
        "biglittle:list"
    )
    item.refresh_from_db()
    assert item.status == PendingPairing.Status.PENDING


def test_the_empty_page_says_so(officer_client):
    response = officer_client.get(reverse("biglittle:review"))

    assert "Nothing is waiting for review." in response.content.decode()


def test_the_list_and_upload_pages_point_managers_at_waiting_rows(officer_client, auto_login_user, chapter, waiting):
    review_url = reverse("biglittle:review")

    assert officer_client.get(reverse("biglittle:list")).context["pending_count"] == 1
    assert review_url in officer_client.get(reverse("biglittle:list")).content.decode()
    assert "1 uploaded row is" in officer_client.get(reverse("biglittle:upload")).content.decode()

    client, _ = auto_login_user(user=_member(chapter, "Plain Member"))
    assert client.get(reverse("biglittle:list")).context["pending_count"] == 0


def test_an_upload_with_names_to_review_links_the_review_page(officer_client, chapter):
    _member(chapter, "Mary Lee")
    upload = SimpleUploadedFile("pairs.csv", (NAMES + "Mary Lee,Jon Smith\n").encode())

    response = officer_client.post(reverse("biglittle:upload"), {"file": upload})

    assert response.context["result"].review_count == 1
    assert "Choose members for 1 row" in response.content.decode()
