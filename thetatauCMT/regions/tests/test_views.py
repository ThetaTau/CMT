import pytest
from django.contrib.auth.models import Group
from django.urls import reverse


def _make_natoff(user, client):
    """Ensure user is in the 'natoff' Django group and refresh the session."""
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


@pytest.mark.django_db
def test_region_list_view_authenticated(auto_login_user):
    client, user = auto_login_user()
    url = reverse("regions:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_region_list_view_unauthenticated(client):
    url = reverse("regions:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_region_redirect_view(auto_login_user):
    client, user = auto_login_user()
    url = reverse("regions:redirect")
    response = client.get(url)
    assert response.status_code == 302
    expected_slug = user.current_chapter.region.slug
    assert f"/regions/{expected_slug}/" in response["Location"]


@pytest.mark.django_db
def test_region_redirect_view_unauthenticated(client):
    url = reverse("regions:redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_region_detail_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    region = user.current_chapter.region
    url = reverse("regions:detail", kwargs={"slug": region.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_region_detail_view_regular_user_redirected(auto_login_user):
    client, user = auto_login_user()
    region = user.current_chapter.region
    url = reverse("regions:detail", kwargs={"slug": region.slug})
    response = client.get(url)
    # Non-natoff users are redirected to home
    assert response.status_code == 302


@pytest.mark.django_db
def test_region_officer_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    region = user.current_chapter.region
    url = reverse("regions:officers", kwargs={"slug": region.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_region_advisor_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    region = user.current_chapter.region
    url = reverse("regions:advisors", kwargs={"slug": region.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_region_task_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    region = user.current_chapter.region
    url = reverse("regions:tasks", kwargs={"slug": region.slug})
    response = client.get(url)
    assert response.status_code == 200
