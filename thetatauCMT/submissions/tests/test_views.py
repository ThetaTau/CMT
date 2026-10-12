import pytest
from django.contrib.auth.models import Group
from django.urls import reverse


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _make_officer(user, client):
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


@pytest.mark.django_db
def test_submission_list_view_authenticated(auto_login_user):
    client, user = auto_login_user()
    url = reverse("submissions:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_submission_list_view_unauthenticated(client):
    url = reverse("submissions:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_submission_create_view_get_returns_form(auto_login_user):
    """Any authenticated user can access the submission create form."""
    client, user = auto_login_user()
    url = reverse("submissions:add")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_submission_create_view_unauthenticated(client):
    url = reverse("submissions:add")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_submission_create_view_renders_datepicker(auto_login_user):
    """Submission Date needs the shared picker; the view used to build a default
    ModelForm from ``fields``, which renders a bare text input."""
    client, user = auto_login_user()
    response = client.get(reverse("submissions:add"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "deferDateTimePicker_id_date()" in body
    assert 'name="date"' in body
    # Without ``{{ form.media }}`` the widget renders but never initialises.
    assert "tempusdominus-bootstrap-4" in body


@pytest.mark.django_db
def test_submission_redirect_view(auto_login_user):
    """Redirect view sends authenticated users to the list."""
    client, user = auto_login_user()
    url = reverse("submissions:redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert "/submissions/" in response["Location"]


@pytest.mark.django_db
def test_submission_redirect_view_unauthenticated(client):
    url = reverse("submissions:redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_gear_article_form_view_authenticated(auto_login_user):
    """Any authenticated user can access the gear article form."""
    client, user = auto_login_user()
    url = reverse("submissions:gear")
    response = client.get(url)
    assert response.status_code == 200


def _gear_article_post_data(user, **overrides):
    """Build a valid POST payload for GearArticleFormView (incl. picture formset)."""
    data = {
        "action": "article",
        "name": "Fall 2026 Chapter Update",
        "authors": [user.pk],
        "article": "<p>Our chapter had a great fall semester.</p>",
        # picture formset management form (default modelformset prefix "form");
        # no per-form data means the lone extra form is left blank/optional.
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_gear_article_form_view_post_valid_creates_submission(auto_login_user):
    """A valid Gear article submission is saved and the user sees a success message."""
    from django.contrib.messages import get_messages

    from thetatauCMT.scores.models import ScoreType
    from thetatauCMT.submissions.models import GearArticle, Submission

    client, user = auto_login_user()
    gear_type = ScoreType.objects.get(name="Gear Article")
    response = client.post(reverse("submissions:gear"), _gear_article_post_data(user))
    assert response.status_code == 302
    assert response["Location"] == reverse("submissions:list")
    assert Submission.objects.filter(type=gear_type, chapter=user.chapter).count() == 1
    assert GearArticle.objects.count() == 1
    rendered_messages = [str(m) for m in get_messages(response.wsgi_request)]
    assert any("was submitted to the Gear editor" in m for m in rendered_messages)


@pytest.mark.django_db
def test_gear_article_form_view_post_invalid_shows_errors(auto_login_user):
    """Missing required fields re-render the page (not a redirect) with visible errors."""
    from thetatauCMT.submissions.models import Submission

    client, user = auto_login_user()
    data = _gear_article_post_data(user, name="", authors=[], article="")
    response = client.post(reverse("submissions:gear"), data)
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "This field is required" in body
    assert not Submission.objects.exists()


@pytest.mark.django_db
def test_gear_article_form_view_post_save_failure_shows_error_not_500(auto_login_user, monkeypatch):
    """A storage/DB failure while saving shows a friendly error instead of a bare
    500, and leaves no partially-created Submission/GearArticle behind."""
    from thetatauCMT.submissions.models import GearArticle, Submission

    def _boom(self, *args, **kwargs):
        raise TimeoutError("simulated storage timeout")

    monkeypatch.setattr(Submission, "save", _boom)
    client, user = auto_login_user()
    response = client.post(reverse("submissions:gear"), _gear_article_post_data(user))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "could not be submitted" in body
    assert not Submission.objects.exists()
    assert not GearArticle.objects.exists()


@pytest.mark.django_db
def test_gear_article_form_view_submissions_link_not_hardcoded(auto_login_user):
    """The 'view submitted gear articles' link filters by the real ScoreType pk
    looked up at request time, not a hard-coded id."""
    from django.utils.html import escape

    from thetatauCMT.scores.models import ScoreType

    client, user = auto_login_user()
    gear_type = ScoreType.objects.get(name="Gear Article")
    response = client.get(reverse("submissions:gear"))
    assert response.status_code == 200
    expected_url = f"{reverse('submissions:list')}?name=&date=&type={gear_type.pk}"
    assert response.context["gear_submissions_url"] == expected_url
    assert escape(expected_url) in response.content.decode("utf-8")


@pytest.mark.django_db
def test_gear_article_list_view_natoff(auto_login_user):
    """GearArticleListView requires natoff group."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("submissions:gearlist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_gear_article_list_view_regular_user_redirected(auto_login_user):
    """Non-natoff users are redirected from GearArticleListView."""
    client, user = auto_login_user()
    url = reverse("submissions:gearlist")
    response = client.get(url)
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# SubmissionUpdateView — GET with plain file (no redirect) (5.7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_submission_update_view_get_officer(auto_login_user):
    """Officers can GET the submission update form for a plain-file submission."""
    from thetatauCMT.scores.models import ScoreType
    from thetatauCMT.submissions.models import Submission

    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    score_type = ScoreType.objects.filter(type="Sub").first()
    if score_type is None:
        pytest.skip("No Sub ScoreType in fixture")
    import datetime

    submission = Submission.objects.create(
        name="Test Submission",
        date=datetime.date.today(),
        type=score_type,
        chapter=user.chapter,
    )
    url = reverse("submissions:update", kwargs={"pk": submission.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_submission_update_view_renders_datepicker(auto_login_user):
    from thetatauCMT.scores.models import ScoreType
    from thetatauCMT.submissions.models import Submission

    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    score_type = ScoreType.objects.filter(type="Sub").first()
    if score_type is None:
        pytest.skip("No Sub ScoreType in fixture")
    import datetime

    submission = Submission.objects.create(
        name="Picker Submission",
        date=datetime.date.today(),
        type=score_type,
        chapter=user.chapter,
    )
    response = client.get(reverse("submissions:update", kwargs={"pk": submission.pk}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "deferDateTimePicker_id_date()" in body
    assert "tempusdominus-bootstrap-4" in body


@pytest.mark.django_db
def test_submission_update_view_get_forms_file_redirects(auto_login_user):
    """GET to update view for a submission with 'forms:' file redirects to that view."""
    from thetatauCMT.scores.models import ScoreType
    from thetatauCMT.submissions.models import Submission

    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    score_type = ScoreType.objects.filter(type="Sub").first()
    if score_type is None:
        pytest.skip("No Sub ScoreType in fixture")
    import datetime

    # Use a forms: URL that resolves without args (forms:rmp)
    submission = Submission.objects.create(
        name="Test RMP Submission",
        date=datetime.date.today(),
        type=score_type,
        chapter=user.chapter,
        file="forms:rmp",
    )
    url = reverse("submissions:update", kwargs={"pk": submission.pk})
    response = client.get(url, follow=False)
    # Accessing a "forms:" submission should redirect to that form URL
    assert response.status_code == 302


@pytest.mark.django_db
def test_submission_create_view_unknown_slug_does_not_crash(auto_login_user):
    """A stale/unknown ScoreType slug must fall back to the default type list,
    not IndexError on ``score_obj[0]`` (issue #1033)."""
    client, user = auto_login_user()
    url = reverse("submissions:add-direct", kwargs={"slug": "no-such-scoretype-slug"})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_submission_detail_view_duplicate_date_slug_no_crash(auto_login_user):
    """Two submissions sharing a date + slug must not raise MultipleObjectsReturned;
    the date + slug detail URL returns the earliest deterministically."""
    import datetime

    from thetatauCMT.scores.models import ScoreType
    from thetatauCMT.submissions.models import Submission

    client, user = auto_login_user()
    score_type = ScoreType.objects.filter(type="Sub").first()
    if score_type is None:
        pytest.skip("No Sub ScoreType in fixture")
    date = datetime.date(2026, 7, 2)
    first = Submission.objects.create(
        name="Risk Management Form Aanika Kumar Nadar",
        date=date,
        type=score_type,
        chapter=user.chapter,
    )
    Submission.objects.create(
        name="Risk Management Form Aanika Kumar Nadar",
        date=date,
        type=score_type,
        chapter=user.chapter,
    )
    url = reverse(
        "submissions:detail",
        kwargs={
            "year": date.year,
            "month": date.month,
            "day": date.day,
            "slug": first.slug,
        },
    )
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["object"].pk == first.pk
