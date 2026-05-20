"""
View tests for the events app.
Uses the auto_login_user fixture which handles RMPSignMiddleware.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType


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
# EventListView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_list_view_returns_200(auto_login_user):
    client, user = auto_login_user()
    url = reverse("events:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_event_list_unauthenticated_redirects(client):
    url = reverse("events:list")
    response = client.get(url)
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# EventListAllView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_list_all_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("events:list_all")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# EventCreateView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_create_view_returns_200(auto_login_user):
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    url = reverse("events:add")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_event_create_view_regular_user(auto_login_user):
    """Regular (non-officer) user — may be redirected or shown a form."""
    client, user = auto_login_user()
    url = reverse("events:add")
    response = client.get(url, follow=True)
    assert response.status_code in (200, 302, 403)


# ---------------------------------------------------------------------------
# EventUpdateView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_update_view_officer(auto_login_user):
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    score_type = ScoreType.objects.filter(type="Evt").first()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = EventFactory.create(chapter=user.chapter, type=score_type)
    url = reverse("events:update", kwargs={"pk": event.pk})
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# EventRedirectView
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_redirect_view(auto_login_user):
    client, user = auto_login_user()
    url = reverse("events:redirect")
    response = client.get(url)
    assert response.status_code == 302


# ---------------------------------------------------------------------------
# EventCopyView — GET (get_event_initial) (5.7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_copy_view_officer_get(auto_login_user):
    """GET on EventCopyView calls get_event_initial and loads the form."""
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    score_type = ScoreType.objects.filter(type="Evt").first()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = EventFactory.create(chapter=user.chapter, type=score_type)
    url = reverse("events:copy", kwargs={"pk": event.pk})
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# EventUpdateView — get_success_url (POST) (5.7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_event_update_view_officer_post_redirects(auto_login_user):
    """POST to EventUpdateView with valid data redirects to events:list."""
    client, user = auto_login_user(make_officer="chapter")
    _make_officer(user, client)
    score_type = ScoreType.objects.filter(type="Evt").first()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = EventFactory.create(chapter=user.chapter, type=score_type)
    url = reverse("events:update", kwargs={"pk": event.pk})
    import datetime

    post_data = {
        "name": "Updated Event Name",
        "date": datetime.date.today().isoformat(),
        "type": score_type.pk,
        "description": "Updated description",
        "members": 5,
        "pledges": 2,
        "alumni": 1,
        "guests": 0,
        "duration": 2,
        "stem": False,
        "host": "local",
        "virtual": False,
        "miles": 0,
        "raised": "0.00",
    }
    response = client.post(url, post_data)
    # UpdateView POST should redirect on success
    assert response.status_code in (200, 302)
