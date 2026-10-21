import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HEADER = "badge_number_big,badge_number_little\n"


@pytest.fixture
def chapter():
    return ChapterFactory(name="alpha")


def _member(chapter, badge, status="active", **kwargs):
    return UserFactory(chapter=chapter, badge_number=badge, current_status=status, **kwargs)


def _import(chapter, text, actor=None, encoding="utf-8"):
    return services.import_big_little_csv(text.encode(encoding), chapter, actor)


def _outcomes(result):
    return [(row.line, row.outcome, row.message) for row in result.rows]


# ---------------------------------------------------------------------------
# The import itself
# ---------------------------------------------------------------------------
def test_rows_are_recorded_and_twins_are_allowed(chapter):
    officer = _member(chapter, 1)
    big = _member(chapter, 101)
    twins = [_member(chapter, 201), _member(chapter, 202)]

    result = _import(chapter, HEADER + "101,201\n101,202\n", actor=officer)

    assert result.error == ""
    assert _outcomes(result) == [(2, "created", "Recorded"), (3, "created", "Recorded")]
    links = BigLittle.objects.current().filter(big=big)
    assert set(links.values_list("little", flat=True)) == {twin.pk for twin in twins}
    assert set(links.values_list("source", "created_by")) == {(BigLittle.Source.UPLOAD, officer.pk)}
    assert result.summary == "Processed 2 row(s): 2 recorded, 0 changed, 0 unchanged, 0 with errors."


def test_a_byte_order_mark_capitals_and_extra_columns_are_fine(chapter):
    big, little = _member(chapter, 101), _member(chapter, 201)

    result = _import(chapter, "\ufeffBadge Number Big,Name,BADGE_NUMBER_LITTLE\n101,Someone,201\n\n")

    assert _outcomes(result) == [(2, "created", "Recorded")]
    assert services.current_big(little) == big


def test_missing_headers_save_nothing(chapter):
    _member(chapter, 101)
    _member(chapter, 201)

    result = _import(chapter, "big,little\n101,201\n")

    assert result.error == "The first row must contain the column names badge_number_big and badge_number_little."
    assert result.rows == []
    assert not BigLittle.objects.exists()


def test_too_many_rows_save_nothing(chapter, monkeypatch):
    monkeypatch.setattr(services, "MAX_UPLOAD_ROWS", 2)
    _member(chapter, 101)

    result = _import(chapter, HEADER + "101,201\n101,202\n101,203\n")

    assert "more than 2 rows" in result.error
    assert not BigLittle.objects.exists()


def test_each_problem_is_reported_on_its_own_line(chapter):
    other = ChapterFactory(name="beta")
    _member(chapter, 101, name="Bo Big")
    _member(chapter, 201, name="Lee Little")
    _member(chapter, 300)
    _member(chapter, 300)
    _member(other, 400)
    _member(chapter, 500, status="pnm", name="Pat Pnm")
    rows = [
        "abc,201",  # 2
        ",201",  # 3
        "999,201",  # 4
        "300,201",  # 5
        "400,201",  # 6
        "101,500",  # 7
        "500,201",  # 8
        "101,101",  # 9
        "101,201",  # 10
        "101,201",  # 11
    ]

    result = _import(chapter, HEADER + "\n".join(rows) + "\n")

    assert _outcomes(result) == [
        (2, "error", '"abc" is not a badge number.'),
        (3, "error", "The Big badge number is missing."),
        (4, "error", "No member of alpha has badge number 999."),
        (5, "error", "More than one member of alpha has badge number 300. Fix the roster first."),
        (6, "error", "No member of alpha has badge number 400."),
        (7, "error", "Pat Pnm is not initiated, so they cannot have a Big yet."),
        (8, "error", "Pat Pnm is not initiated, so they cannot be a Big."),
        (9, "error", "A member cannot be their own Big."),
        (10, "created", "Recorded"),
        (11, "error", "Lee Little is already listed on line 10."),
    ]


def test_a_loop_inside_the_file_is_refused_on_its_line(chapter):
    _member(chapter, 601, name="Ann One")
    _member(chapter, 602, name="Ben Two")

    result = _import(chapter, HEADER + "601,602\n602,601\n")

    assert _outcomes(result)[0] == (2, "created", "Recorded")
    assert _outcomes(result)[1][:2] == (3, "error")
    assert "further down" in _outcomes(result)[1][2]


def test_a_different_big_replaces_the_old_one_and_says_so(chapter):
    old_big, new_big = _member(chapter, 101, name="Old Big"), _member(chapter, 102)
    little = _member(chapter, 201)
    services.set_big(little, old_big, source=BigLittle.Source.MEMBER)

    result = _import(chapter, HEADER + "102,201\n")

    assert _outcomes(result) == [(2, "changed", "Changed (was Old Big)")]
    assert services.current_big(little) == new_big
    assert little.links_as_little.former().get().big == old_big


def test_uploading_the_same_file_twice_changes_nothing(chapter):
    _member(chapter, 101)
    _member(chapter, 201)
    text = HEADER + "101,201\n"
    _import(chapter, text)

    again = _import(chapter, text)

    assert _outcomes(again) == [(2, "unchanged", "No change")]
    assert BigLittle.objects.count() == 1


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------
@pytest.fixture
def officer_client(auto_login_user, chapter):
    client, officer = auto_login_user(user=_member(chapter, 1))
    officer.groups.add(Group.objects.get_or_create(name="officer")[0])
    return client


def _upload(client, content, name="pairs.csv"):
    return client.post(reverse("biglittle:upload"), {"file": SimpleUploadedFile(name, content)})


def test_the_page_shows_results_after_an_upload(officer_client, chapter):
    _member(chapter, 101)
    _member(chapter, 201)

    response = _upload(officer_client, (HEADER + "101,201\n999,201\n").encode())

    assert response.status_code == 200
    assert [row.outcome for row in response.context["result"].rows] == ["created", "error"]
    content = response.content.decode()
    assert "No member of alpha has badge number 999." in content
    assert "Rows with problems were not saved." in content


@pytest.mark.parametrize(
    "name, content, error",
    [
        ("pairs.txt", HEADER.encode(), "Please upload a .csv file."),
        ("pairs.csv", b"x" * (5 * 1024 * 1024 + 1), "The file is too large (5 MB at most)."),
        ("pairs.csv", b"big,little\n", "The first row must contain the column names"),
    ],
)
def test_the_page_refuses_bad_files(officer_client, name, content, error):
    response = _upload(officer_client, content, name)

    assert response.status_code == 200
    assert error in " ".join(response.context["form"].errors["file"])
    assert not BigLittle.objects.exists()


def test_a_plain_member_is_turned_away(auto_login_user, chapter):
    client, _ = auto_login_user(user=_member(chapter, 1))

    assert client.get(reverse("biglittle:upload")).url == reverse("biglittle:list")
    assert client.get(reverse("biglittle:upload_template")).url == reverse("biglittle:list")


def test_the_template_has_the_two_headers(officer_client):
    response = officer_client.get(reverse("biglittle:upload_template"))

    assert response.content == b"badge_number_big,badge_number_little\r\n"
    assert response["Content-Disposition"] == 'attachment; filename="big_little_template.csv"'
