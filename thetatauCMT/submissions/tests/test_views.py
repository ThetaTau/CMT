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
