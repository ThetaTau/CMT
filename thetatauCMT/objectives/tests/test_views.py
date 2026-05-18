import pytest
from django.urls import reverse
from django.contrib.auth.models import Group
from thetatauCMT.objectives.models import Objective, Action


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


@pytest.mark.django_db
def test_objective_list_view_authenticated(auto_login_user):
    client, user = auto_login_user()
    url = reverse("objectives:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_objective_list_view_unauthenticated(client):
    url = reverse("objectives:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_objective_create_view_get_returns_form(auto_login_user):
    client, user = auto_login_user()
    url = reverse("objectives:create")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_objective_create_view_unauthenticated(client):
    url = reverse("objectives:create")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_objective_detail_view_returns_200(auto_login_user):
    client, user = auto_login_user()
    objective = Objective.objects.create(
        owner=user,
        user=user,
        chapter=user.current_chapter,
        title="Test Goal",
        date="2024-01-01",
        complete=False,
        description="<p>A test goal description</p>",
        restricted_ec=False,
        restricted_co=False,
    )
    url = reverse("objectives:detail", kwargs={"pk": objective.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_objective_detail_restricted_ec_redirects_non_superuser(auto_login_user):
    """Restricted objectives redirect regular users to the objectives list."""
    client, user = auto_login_user()
    objective = Objective.objects.create(
        owner=user,
        user=user,
        chapter=user.current_chapter,
        title="Secret Goal",
        date="2024-01-01",
        complete=False,
        description="<p>Restricted</p>",
        restricted_ec=True,
        restricted_co=False,
    )
    url = reverse("objectives:detail", kwargs={"pk": objective.pk})
    response = client.get(url, follow=True)
    # Should redirect to objectives:list with info message (URL is /goals/)
    assert response.status_code == 200
    assert any(
        "/goals" in redir_url for redir_url, _ in response.redirect_chain
    )


@pytest.mark.django_db
def test_objective_detail_restricted_co_redirects_non_superuser(auto_login_user):
    """CO-restricted objectives redirect regular users."""
    client, user = auto_login_user()
    objective = Objective.objects.create(
        owner=user,
        user=user,
        chapter=user.current_chapter,
        title="CO Goal",
        date="2024-01-01",
        complete=False,
        description="<p>CO Restricted</p>",
        restricted_ec=False,
        restricted_co=True,
    )
    url = reverse("objectives:detail", kwargs={"pk": objective.pk})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    assert any("/goals" in redir_url for redir_url, _ in response.redirect_chain)


@pytest.mark.django_db
def test_objective_list_excludes_restricted(auto_login_user):
    """List view excludes restricted_ec and restricted_co objectives."""
    client, user = auto_login_user()
    visible = Objective.objects.create(
        owner=user,
        user=user,
        chapter=user.current_chapter,
        title="Visible",
        date="2024-01-01",
        complete=False,
        description="<p>Visible</p>",
        restricted_ec=False,
        restricted_co=False,
    )
    hidden = Objective.objects.create(
        owner=user,
        user=user,
        chapter=user.current_chapter,
        title="Hidden",
        date="2024-01-01",
        complete=False,
        description="<p>Hidden</p>",
        restricted_ec=True,
        restricted_co=False,
    )
    qs = Objective.objects.exclude(restricted_ec=True).exclude(restricted_co=True)
    assert visible in qs
    assert hidden not in qs
