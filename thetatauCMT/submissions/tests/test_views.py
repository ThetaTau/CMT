import pytest
from django.urls import reverse
from django.contrib.auth.models import Group


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
    from thetatauCMT.submissions.models import Submission
    from thetatauCMT.scores.models import ScoreType
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
    from thetatauCMT.submissions.models import Submission
    from thetatauCMT.scores.models import ScoreType
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
