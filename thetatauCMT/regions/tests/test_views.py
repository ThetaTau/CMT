import pytest
from django.contrib.auth.models import Group
from django.urls import reverse


def _make_natoff(user, client):
    """Ensure user is in the 'natoff' Django group and refresh the session."""
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _make_region_officer(chapter, role, email):
    """Create an officer in ``chapter`` holding ``role`` with ``email``."""
    from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory

    officer = UserFactory.create(chapter=chapter, email=email)
    UserRoleChangeFactory.create(user=officer, role=role, current=True)
    officer.refresh_from_db()
    current = set(officer.current_roles or [])
    current.add(role)
    officer.current_roles = list(current)
    officer.save(update_fields=["current_roles"])
    return officer


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
def test_region_detail_view_regular_user_can_view(auto_login_user):
    """The region detail page is open to any authenticated member."""
    client, user = auto_login_user()
    region = user.current_chapter.region
    url = reverse("regions:detail", kwargs={"slug": region.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_region_detail_shows_directors_and_chapters(auto_login_user):
    """Detail page lists the regional director(s), chapters, and region info."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.regions.tests.factories import RegionFactory
    from thetatauCMT.users.tests.factories import UserFactory

    client, user = auto_login_user()
    region = RegionFactory(name="Detailed Region")
    director = UserFactory(first_name="Rita", last_name="Director")
    region.directors.add(director)
    # ChapterFactory uses django_get_or_create=("name",); set the region
    # explicitly after creation so a name collision can't drop a region= kwarg.
    chapter = ChapterFactory()
    chapter.region = region
    chapter.save(update_fields=["region"])

    url = reverse("regions:detail", kwargs={"slug": region.slug})
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode("UTF-8")
    assert "Detailed Region" in content
    assert reverse("users:profile", kwargs={"username": director.username}) in content
    assert director.name in content
    assert reverse("chapters:detail", kwargs={"slug": chapter.slug}) in content
    assert region.email in content  # generic region contact
    assert list(response.context["directors"]) == [director]
    assert chapter in list(response.context["chapters"])


@pytest.mark.django_db
def test_region_dashboard_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    region = user.current_chapter.region
    url = reverse("regions:dashboard", kwargs={"slug": region.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_region_dashboard_view_regular_user_redirected(auto_login_user):
    client, user = auto_login_user()
    region = user.current_chapter.region
    url = reverse("regions:dashboard", kwargs={"slug": region.slug})
    response = client.get(url)
    # Non-natoff users are redirected to home (dashboard stays natoff-only).
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


@pytest.mark.django_db
def test_region_officer_view_email_list_includes_generic(auto_login_user):
    """Region officers "Copy emails" includes each officer's generic chapter mailbox."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    region = user.current_chapter.region
    chapter = ChapterFactory(region=region)
    # Set explicitly so a ChapterFactory name collision returning an existing
    # chapter can't drop the generic mailbox value.
    chapter.email_regent = "regent@generic.example.com"
    chapter.save(update_fields=["email_regent"])
    _make_region_officer(chapter, "regent", "regentperson@example.com")
    url = reverse("regions:officers", kwargs={"slug": region.slug})
    response = client.get(url)
    assert response.status_code == 200
    email_list = response.context["email_list"]
    assert "regentperson@example.com" in email_list
    assert "regent@generic.example.com" in email_list
    # The generic mailbox stays associated with the officer for the CSV export.
    assert response.context["email_generic_map"]["regentperson@example.com"] == "regent@generic.example.com"


@pytest.mark.django_db
def test_region_officer_view_csv_includes_generic_column(auto_login_user):
    """The officer CSV export gains a Generic Officer Email column."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    region = user.current_chapter.region
    chapter = ChapterFactory(region=region)
    # Set explicitly so a ChapterFactory name collision returning an existing
    # chapter can't drop the generic mailbox value.
    chapter.email_regent = "regent@generic.example.com"
    chapter.save(update_fields=["email_regent"])
    _make_region_officer(chapter, "regent", "regentperson@example.com")
    url = reverse("regions:officers", kwargs={"slug": region.slug})
    response = client.get(url, {"csv": "download csv", "region": region.slug})
    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    content = response.content.decode("utf-8")
    assert "Generic Officer Email" in content
    assert "regent@generic.example.com" in content
    assert "regentperson@example.com" in content
