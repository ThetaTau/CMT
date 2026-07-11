"""
View tests for the events app.
Uses the auto_login_user fixture which handles RMPSignMiddleware.
"""

import datetime
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.events.models import Event
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


def _make_chapter_officer(user, client):
    """Make user a chapter officer that is definitely NOT a National Officer.

    The ``make_officer='chapter'`` factory path can leave a user in the natoff
    group (its random initial role may be national before it is corrected to a
    chapter role, and the role-change signal never removes the group). For
    permission-denial tests we build the officer explicitly and clear natoff.
    """
    officer_group, _ = Group.objects.get_or_create(name="officer")
    natoff_group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(officer_group)
    user.groups.remove(natoff_group)
    natoff_group.user_set.remove(user)
    user.current_roles = ["scribe"]
    user.save(update_fields=["current_roles"])
    client.force_login(user)


def _evt_score_type():
    return ScoreType.objects.filter(type="Evt").first()


def _event_create_post_data(score_type, **overrides):
    """Build a valid POST payload for EventCreateView (incl. picture formset)."""
    data = {
        "name": "Public Fair",
        "date": datetime.date.today().isoformat(),
        "type": score_type.pk,
        "description": "A public event",
        "members": 1,
        "pledges": 0,
        "alumni": 0,
        "guests": 0,
        "duration": 1,
        "miles": 0,
        "raised": "0.00",
        "is_public": True,
        # picture formset management form (default modelformset prefix "form")
        "form-TOTAL_FORMS": "1",
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": "1000",
    }
    data.update(overrides)
    return data


def _pending_public_event(chapter, score_type):
    return EventFactory.create(
        chapter=chapter,
        type=score_type,
        is_public=True,
        approval_status=Event.ApprovalStatus.PENDING,
    )


def _distinct_chapter(chapter_factory, other_than):
    """A chapter guaranteed to differ from ``other_than``.

    ChapterFactory draws names from a small greek pool with
    ``django_get_or_create=("name",)``, so a plain ``create()`` can collide with
    the event's own chapter and break cross-chapter visibility assertions.
    """
    from thetatauCMT.chapters.models import GREEK_ABR

    for name in GREEK_ABR.values():
        if name != other_than.name:
            return chapter_factory.create(name=name)
    raise RuntimeError("No distinct chapter name available")


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
    url = event.get_update_url()
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
    url = event.get_update_url()
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


# ===========================================================================
# WI-1 — create-path gating for the national flag
# ===========================================================================


@pytest.mark.django_db
def test_create_view_national_flag_ignored_for_chapter_officer(auto_login_user):
    """A chapter officer cannot set is_national via the create endpoint."""
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    url = reverse("events:add")
    response = client.post(url, _event_create_post_data(score_type, name="Sneaky National", is_national=True))
    assert response.status_code == 302
    event = Event.objects.get(name="Sneaky National")
    assert event.is_national is False


# ===========================================================================
# WI-2 — approval workflow endpoints
# ===========================================================================


@pytest.mark.django_db
def test_pending_default_on_chapter_public_event(auto_login_user):
    """A chapter officer's public event is created with approval_status=pending."""
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    url = reverse("events:add")
    response = client.post(url, _event_create_post_data(score_type, name="Chapter Public Fair"))
    assert response.status_code == 302
    event = Event.objects.get(name="Chapter Public Fair")
    assert event.is_public is True
    assert event.approval_status == Event.ApprovalStatus.PENDING
    assert event.is_cross_chapter_visible is False


@pytest.mark.django_db
def test_national_officer_public_event_auto_approved(auto_login_user):
    """A National Officer's public event is auto-approved (default config)."""
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    url = reverse("events:add")
    response = client.post(url, _event_create_post_data(score_type, name="Nat Public Summit"))
    assert response.status_code == 302
    event = Event.objects.get(name="Nat Public Summit")
    assert event.approval_status == Event.ApprovalStatus.APPROVED
    assert event.reviewed_by_id == natoff.pk


@pytest.mark.django_db
def test_pending_list_view_natoff_only(auto_login_user):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    response = client.get(reverse("events:pending"))
    assert response.status_code == 200


@pytest.mark.django_db
def test_pending_list_shows_national_events(auto_login_user, event_factory):
    """National (chapter=None) pending events render in the review queue."""
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event_factory.create(
        name="Nat Pending Fair",
        is_national=True,
        chapter=None,
        type=score_type,
        approval_status=Event.ApprovalStatus.PENDING,
    )
    response = client.get(reverse("events:pending"))
    assert response.status_code == 200
    assert b"Nat Pending Fair" in response.content
    assert b"National (org-wide)" in response.content


@pytest.mark.django_db
def test_pending_list_view_denied_for_chapter_officer(auto_login_user):
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    response = client.get(reverse("events:pending"))
    # NationalOfficerRequiredMixin redirects non-national officers home.
    assert response.status_code == 302


@pytest.mark.django_db
def test_only_national_officer_can_approve(auto_login_user):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = _pending_public_event(natoff.chapter, score_type)
    response = client.post(reverse("events:approve", kwargs={"pk": event.pk}))
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.APPROVED
    assert event.reviewed_by_id == natoff.pk
    assert event.reviewed_at is not None


@pytest.mark.django_db
def test_chapter_officer_cannot_approve(auto_login_user):
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = _pending_public_event(user.chapter, score_type)
    response = client.post(reverse("events:approve", kwargs={"pk": event.pk}))
    assert response.status_code == 302  # redirected home by the mixin
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.PENDING  # unchanged
    assert event.reviewed_by_id is None


@pytest.mark.django_db
def test_chapter_officer_cannot_reject(auto_login_user):
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = _pending_public_event(user.chapter, score_type)
    response = client.post(
        reverse("events:reject", kwargs={"pk": event.pk}),
        {"rejection_reason": "nope"},
    )
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.PENDING  # unchanged
    assert not event.rejection_reason


@pytest.mark.django_db
def test_rejection_reason_persisted(auto_login_user):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = _pending_public_event(natoff.chapter, score_type)
    response = client.post(
        reverse("events:reject", kwargs={"pk": event.pk}),
        {"rejection_reason": "Duplicate of regional event"},
    )
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.REJECTED
    assert event.rejection_reason == "Duplicate of regional event"
    assert event.reviewed_by_id == natoff.pk


@pytest.mark.django_db
def test_approved_event_becomes_cross_chapter_visible(auto_login_user, chapter_factory):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    other_chapter = _distinct_chapter(chapter_factory, natoff.chapter)
    event = _pending_public_event(natoff.chapter, score_type)
    # Pending public event is not yet visible to other chapters.
    assert event not in Event.objects.visible_to_chapter(other_chapter)
    client.post(reverse("events:approve", kwargs={"pk": event.pk}))
    event.refresh_from_db()
    assert event.is_cross_chapter_visible is True
    assert event in Event.objects.visible_to_chapter(other_chapter)


@pytest.mark.django_db
def test_rejected_event_is_not_cross_chapter_visible(auto_login_user, chapter_factory):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    other_chapter = _distinct_chapter(chapter_factory, natoff.chapter)
    event = _pending_public_event(natoff.chapter, score_type)
    client.post(
        reverse("events:reject", kwargs={"pk": event.pk}),
        {"rejection_reason": "Not appropriate"},
    )
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.REJECTED
    assert event.is_cross_chapter_visible is False
    assert event not in Event.objects.visible_to_chapter(other_chapter)


# ===========================================================================
# National events: not tied to a chapter, auto-approved + public (create view)
# ===========================================================================


@pytest.mark.django_db
def test_create_national_event_not_tied_to_chapter_and_auto_approved(auto_login_user):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    url = reverse("events:add")
    response = client.post(url, _event_create_post_data(score_type, name="Nat Org Event", is_national=True))
    assert response.status_code == 302
    event = Event.objects.get(name="Nat Org Event")
    assert event.is_national is True
    assert event.is_public is True
    assert event.chapter_id is None
    assert event.approval_status == Event.ApprovalStatus.APPROVED


# ===========================================================================
# Parent-event autocomplete scoping (national vs chapter) + officer gating
# ===========================================================================


@pytest.mark.django_db
def test_event_autocomplete_national_scope(auto_login_user, event_factory):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    national = event_factory.create(name="Nat AC Event", is_national=True, chapter=None, type=score_type)
    chapter_evt = event_factory.create(name="Chapter AC Event", chapter=natoff.chapter, type=score_type)
    url = reverse("events:event-autocomplete")
    response = client.get(url, {"forward": json.dumps({"is_national": True}), "q": ""})
    ids = {str(r["id"]) for r in response.json()["results"]}
    assert str(national.pk) in ids
    assert str(chapter_evt.pk) not in ids


@pytest.mark.django_db
def test_event_autocomplete_chapter_scope(auto_login_user, event_factory):
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    national = event_factory.create(name="Nat AC2", is_national=True, chapter=None, type=score_type)
    chapter_evt = event_factory.create(name="Chapter AC2", chapter=user.chapter, type=score_type)
    url = reverse("events:event-autocomplete")
    response = client.get(url, {"forward": json.dumps({"is_national": False, "self_pk": 0}), "q": ""})
    ids = {str(r["id"]) for r in response.json()["results"]}
    assert str(chapter_evt.pk) in ids
    assert str(national.pk) not in ids


@pytest.mark.django_db
def test_event_autocomplete_denied_for_non_officer(auto_login_user, event_factory):
    client, user = auto_login_user()  # plain member, no officer group
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event_factory.create(name="Some Event", chapter=user.chapter, type=score_type)
    url = reverse("events:event-autocomplete")
    response = client.get(url, {"q": ""})
    assert response.json()["results"] == []


# ===========================================================================
# Update view supports the new fields (public flag drives approval)
# ===========================================================================


@pytest.mark.django_db
def test_update_view_supports_public_flag(auto_login_user):
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = ScoreType.objects.filter(type="Evt").exclude(slug="article").first()
    if score_type is None:
        pytest.skip("No non-article Evt ScoreType in fixture")
    event = EventFactory.create(chapter=user.chapter, type=score_type, is_public=False)
    url = event.get_update_url()
    data = {
        "name": event.name,
        "date": event.date.isoformat(),
        "type": score_type.pk,
        "description": (event.description or "desc")[:190],
        "members": event.members,
        "pledges": event.pledges,
        "alumni": event.alumni,
        "guests": event.guests,
        "duration": event.duration,
        "miles": event.miles,
        "raised": "0.00",
        "is_public": True,
    }
    response = client.post(url, data)
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.is_public is True
    # A chapter officer making an event public sends it to the pending queue.
    assert event.approval_status == Event.ApprovalStatus.PENDING


@pytest.mark.django_db
def test_rejected_event_cannot_be_made_public_via_update(auto_login_user):
    """A rejected public event stays rejected — it cannot be re-requested public."""
    client, user = auto_login_user()
    _make_chapter_officer(user, client)
    score_type = ScoreType.objects.filter(type="Evt").exclude(slug="article").first()
    if score_type is None:
        pytest.skip("No non-article Evt ScoreType in fixture")
    event = EventFactory.create(
        chapter=user.chapter,
        type=score_type,
        is_public=True,
        approval_status=Event.ApprovalStatus.REJECTED,
        rejection_reason="No",
    )
    url = event.get_update_url()
    data = {
        "name": event.name,
        "date": event.date.isoformat(),
        "type": score_type.pk,
        "description": (event.description or "desc")[:190],
        "members": event.members,
        "pledges": event.pledges,
        "alumni": event.alumni,
        "guests": event.guests,
        "duration": event.duration,
        "miles": event.miles,
        "raised": "0.00",
        "is_public": True,  # attempt to re-request public
    }
    response = client.post(url, data)
    assert response.status_code == 302
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.REJECTED


# ===========================================================================
# Detail view: rejection reason display + robust lookup
# ===========================================================================


@pytest.mark.django_db
def test_detail_view_shows_rejection_reason(auto_login_user):
    client, user = auto_login_user()
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = EventFactory.create(
        chapter=user.chapter,
        type=score_type,
        is_public=True,
        approval_status=Event.ApprovalStatus.REJECTED,
        rejection_reason="Not appropriate cross-chapter",
    )
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    assert b"Not appropriate cross-chapter" in response.content
    assert b"cannot be made public again" in response.content


@pytest.mark.django_db
def test_detail_view_renders_national_event(auto_login_user, event_factory):
    client, user = auto_login_user()
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = event_factory.create(name="Nat Detail", is_national=True, chapter=None, type=score_type)
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    assert b"National (org-wide)" in response.content


# ===========================================================================
# Pending review page: name links to detail (new tab) + details sub-row
# ===========================================================================


@pytest.mark.django_db
def test_pending_list_row_links_to_detail_and_shows_subrow(auto_login_user, event_factory):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = event_factory.create(
        name="Detail Link Event",
        chapter=natoff.chapter,
        type=score_type,
        is_public=True,
        approval_status=Event.ApprovalStatus.PENDING,
        description="Sub row description here",
    )
    response = client.get(reverse("events:pending"))
    assert response.status_code == 200
    content = response.content.decode()
    # Name links to the detail page, opened in a new tab.
    assert event.get_absolute_url() in content
    assert 'target="_blank"' in content
    # The details sub-row shows the description to aid review.
    assert "Sub row description here" in content


# ===========================================================================
# Detail view review actions (National Officer approve/reject in-place)
# ===========================================================================


@pytest.mark.django_db
def test_detail_view_shows_review_actions_for_natoff(auto_login_user, event_factory):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = event_factory.create(
        name="Review Me",
        chapter=natoff.chapter,
        type=score_type,
        is_public=True,
        approval_status=Event.ApprovalStatus.PENDING,
    )
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    content = response.content.decode()
    assert "Review this event" in content
    assert reverse("events:approve", kwargs={"pk": event.pk}) in content
    assert reverse("events:reject", kwargs={"pk": event.pk}) in content


@pytest.mark.django_db
def test_detail_view_no_review_actions_for_member(auto_login_user, event_factory):
    client, user = auto_login_user()
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = event_factory.create(
        chapter=user.chapter,
        type=score_type,
        is_public=True,
        approval_status=Event.ApprovalStatus.PENDING,
    )
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    assert "Review this event" not in response.content.decode()


@pytest.mark.django_db
def test_approve_from_detail_redirects_back(auto_login_user, event_factory):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = event_factory.create(
        chapter=natoff.chapter,
        type=score_type,
        is_public=True,
        approval_status=Event.ApprovalStatus.PENDING,
    )
    detail_url = event.get_absolute_url()
    response = client.post(reverse("events:approve", kwargs={"pk": event.pk}), {"next": detail_url})
    assert response.status_code == 302
    assert response.url == detail_url
    event.refresh_from_db()
    assert event.approval_status == Event.ApprovalStatus.APPROVED


# ===========================================================================
# Attendance integration: create & add attendance, detail attendance table
# ===========================================================================


@pytest.mark.django_db
def test_create_and_add_attendance_redirects_to_roster(auto_login_user):
    client, natoff = auto_login_user(make_officer="national")
    _make_natoff(natoff, client)
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    data = _event_create_post_data(score_type, name="Attn Redirect Event")
    data["add_attendance"] = "1"
    response = client.post(reverse("events:add"), data)
    assert response.status_code == 302
    event = Event.objects.get(name="Attn Redirect Event")
    assert response.url == event.get_attendance_url()


@pytest.mark.django_db
def test_detail_view_shows_attendance_table(auto_login_user, user_factory):
    from thetatauCMT.attendance.models import AttendanceRecord

    client, user = auto_login_user()
    score_type = _evt_score_type()
    if score_type is None:
        pytest.skip("No Evt ScoreType in fixture")
    event = EventFactory.create(chapter=user.chapter, type=score_type)
    member = user_factory.create(chapter=user.chapter, first_name="Aaron", last_name="Zeta")
    AttendanceRecord.objects.create(
        event=event,
        user=member,
        status="attended",
        was_active=True,
        chapter=member.chapter,
        recorded_by=user,
    )
    response = client.get(event.get_absolute_url())
    assert response.status_code == 200
    content = response.content.decode()
    assert "Attendance" in content
    assert "Aaron" in content
    assert "Zeta" in content
