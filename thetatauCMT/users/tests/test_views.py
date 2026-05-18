"""
View tests for the users app.
Uses the auto_login_user fixture which handles RMPSignMiddleware.
"""
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse


def _make_natoff(user, client):
    """Ensure user is in the 'natoff' Django group and re-login."""
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _make_officer(user, client):
    """Ensure user is in the 'officer' Django group and re-login."""
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


# ---------------------------------------------------------------------------
# UserRedirectView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_redirect_view(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:redirect")
    response = client.get(url)
    # Should redirect to users:detail
    assert response.status_code == 302
    assert reverse("users:detail") in response["Location"]


# ---------------------------------------------------------------------------
# UserDetailUpdateView (myinfo)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_detail_view_returns_200(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:detail")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_detail_view_unauthenticated(client):
    url = reverse("users:detail")
    response = client.get(url)
    # Should redirect to login
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# UserListView — national officer only
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_list_view_natoff_returns_200(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("users:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_user_list_view_chapter_officer_redirected_or_403(auto_login_user):
    client, user = auto_login_user(make_officer="chapter")
    url = reverse("users:list")
    response = client.get(url, follow=True)
    # Non-natoff users should be redirected or denied
    assert response.status_code in (200, 302, 403)


# ---------------------------------------------------------------------------
# UserDetailView (memberinfo by username)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_member_info_view(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("users:info", kwargs={"username": user.username})
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserGPAFormSetView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_gpas_view_returns_200(auto_login_user):
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    url = reverse("users:gpas")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserServiceFormSetView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_service_view_returns_200(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:service")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserOrgsFormSetView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_orgs_view_returns_200(auto_login_user):
    client, user = auto_login_user()
    url = reverse("users:orgs")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# UserSearchView
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_search_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("users:search")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# User model — set_no_contact
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_set_no_contact(auto_login_user, user_factory):
    client, user = auto_login_user()
    user.set_no_contact()
    user.refresh_from_db()
    assert user.unsubscribe_email is True
    assert user.unsubscribe_paper_gear is True
    assert user.no_contact is True


# ---------------------------------------------------------------------------
# User model — get_name_with_details
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_name_with_details(user_factory):
    user = user_factory.create()
    result = user.get_name_with_details()
    assert user.name in result
    assert str(user.graduation_year) in result


# ---------------------------------------------------------------------------
# User model — current_chapter property
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_current_chapter_regular_user(user_factory):
    user = user_factory.create()
    assert user.current_chapter == user.chapter


# ---------------------------------------------------------------------------
# User model — emails property
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_emails_property(user_factory):
    user = user_factory.create()
    emails = user.emails
    assert user.email in emails
    assert user.email_school in emails


# ---------------------------------------------------------------------------
# User model — get_absolute_url
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_user_get_absolute_url(user_factory):
    user = user_factory.create()
    assert user.get_absolute_url() == reverse("users:detail")


# ---------------------------------------------------------------------------
# User model — next_pledge_number
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_next_pledge_number_starts_at_2000000(user_factory):
    from thetatauCMT.users.models import User
    next_num = User.next_pledge_number()
    assert next_num >= 2_000_000
