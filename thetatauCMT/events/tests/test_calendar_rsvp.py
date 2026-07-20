"""WI-10 tests — public events calendar + cross-chapter RSVP.

Acceptance criteria covered by name:
    * only approved public events shown cross-chapter
    * pending / rejected public events excluded
    * region + chapter filters
    * RSVP creates a signed_up AttendanceRecord
    * past events cannot be RSVP'd (only attendance can be added)
    * WI-6 privacy — cross-chapter viewers do not see the roster
    * chapter detail page lists upcoming public events
"""

import datetime
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.attendance.models import AttendanceRecord
from thetatauCMT.attendance.tests.factories import AttendanceRecordFactory
from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.tests.factories import UserFactory

TODAY = timezone.localdate()
FUTURE = TODAY + datetime.timedelta(days=5)
PAST = TODAY - datetime.timedelta(days=40)


def _evt_score_type():
    return ScoreType.objects.filter(type="Evt").first()


def _event(chapter, name, date=FUTURE, **kwargs):
    return EventFactory.create(chapter=chapter, type=_evt_score_type(), date=date, name=name, **kwargs)


def _chapters(chapter_factory, n):
    """``n`` distinct chapters (distinct Greek names → no get_or_create collision)."""
    greek = list(GREEK_ABR.values())
    return [chapter_factory.create(name=greek[i]) for i in range(n)]


def _cal_url(**params):
    url = reverse("events:calendar")
    return f"{url}?{urlencode(params)}" if params else url


def _month(d):
    return f"{d.year}-{d.month:02d}"


# ===========================================================================
# Cross-chapter visibility (reuses WI-2 visible_to_chapter)
# ===========================================================================


@pytest.mark.django_db
def test_calendar_shows_own_and_approved_public_events(auto_login_user, chapter_factory):
    ch_x, ch_y = _chapters(chapter_factory, 2)
    _event(ch_x, "My Own Event")  # own chapter, not public
    _event(ch_y, "Other Public Event", is_public=True, approval_status="approved")
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch_x, name="Cal Viewer"))

    response = client.get(_cal_url(month=_month(FUTURE)))

    assert response.status_code == 200
    names = [e.name for e in response.context["events"]]
    assert "My Own Event" in names
    assert "Other Public Event" in names


@pytest.mark.django_db
def test_calendar_excludes_pending_and_rejected_public_events(auto_login_user, chapter_factory):
    ch_x, ch_y, ch_z = _chapters(chapter_factory, 3)
    _event(ch_y, "Pending Public", is_public=True, approval_status="pending")
    _event(ch_z, "Rejected Public", is_public=True, approval_status="rejected")
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch_x, name="Cal Excl Viewer"))

    response = client.get(_cal_url(month=_month(FUTURE)))

    names = [e.name for e in response.context["events"]]
    assert "Pending Public" not in names
    assert "Rejected Public" not in names


# ===========================================================================
# Filters
# ===========================================================================


@pytest.mark.django_db
def test_calendar_region_filter(auto_login_user, chapter_factory):
    region_a = RegionFactory.create(name="Region A Ten")
    region_b = RegionFactory.create(name="Region B Ten")
    greek = list(GREEK_ABR.values())
    ch_a = chapter_factory.create(name=greek[0], region=region_a)
    ch_b = chapter_factory.create(name=greek[1], region=region_b)
    _event(ch_a, "Region A Public", is_public=True, approval_status="approved")
    _event(ch_b, "Region B Public", is_public=True, approval_status="approved")
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch_a, name="Region Filter Viewer"))

    response = client.get(_cal_url(month=_month(FUTURE), region=region_a.slug))

    names = [e.name for e in response.context["events"]]
    assert "Region A Public" in names
    assert "Region B Public" not in names


@pytest.mark.django_db
def test_calendar_chapter_filter(auto_login_user, chapter_factory):
    ch_a, ch_b = _chapters(chapter_factory, 2)
    _event(ch_a, "Chapter A Public", is_public=True, approval_status="approved")
    _event(ch_b, "Chapter B Public", is_public=True, approval_status="approved")
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch_a, name="Chapter Filter Viewer"))

    response = client.get(_cal_url(month=_month(FUTURE), chapter=ch_b.slug))

    names = [e.name for e in response.context["events"]]
    assert "Chapter B Public" in names
    assert "Chapter A Public" not in names


@pytest.mark.django_db
def test_calendar_table_view(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    _event(ch, "Table View Event", is_public=True, approval_status="approved")
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch, name="Table Viewer"))

    response = client.get(_cal_url(month=_month(FUTURE), view="table"))

    assert response.status_code == 200
    assert response.context["view_mode"] == "table"
    assert b'id="events-table"' in response.content
    assert b"Table View Event" in response.content


# ===========================================================================
# RSVP action
# ===========================================================================


@pytest.mark.django_db
def test_rsvp_creates_signed_up_record(auto_login_user, chapter_factory):
    ch_host, ch_member = _chapters(chapter_factory, 2)
    event = _event(ch_host, "RSVP Event", is_public=True, approval_status="approved")
    member = UserFactory.create(chapter=ch_member, name="RSVP Member")
    client, _ = auto_login_user(user=member)

    response = client.post(event.get_rsvp_url())

    assert response.status_code == 302
    record = AttendanceRecord.objects.get(event=event, user=member)
    assert record.status == AttendanceRecord.STATUS.SIGNED_UP
    assert record.chapter_id == ch_member.pk  # snapshot of the member's home chapter


@pytest.mark.django_db
def test_rsvp_rejected_for_past_event(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Past Event", date=PAST, is_public=True, approval_status="approved")
    member = UserFactory.create(chapter=ch, name="Past RSVP Member")
    client, _ = auto_login_user(user=member)

    response = client.post(event.get_rsvp_url())

    assert response.status_code == 302
    assert not AttendanceRecord.objects.filter(event=event, user=member).exists()


@pytest.mark.django_db
def test_rsvp_rejected_for_pending_cross_chapter_event(auto_login_user, chapter_factory):
    ch_host, ch_member = _chapters(chapter_factory, 2)
    event = _event(ch_host, "Pending RSVP Event", is_public=True, approval_status="pending")
    member = UserFactory.create(chapter=ch_member, name="NonVisible RSVP Member")
    client, _ = auto_login_user(user=member)

    response = client.post(event.get_rsvp_url())

    assert response.status_code == 302
    assert not AttendanceRecord.objects.filter(event=event, user=member).exists()


@pytest.mark.django_db
def test_rsvp_does_not_downgrade_attended(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Attended RSVP Event", is_public=True, approval_status="approved")
    member = UserFactory.create(chapter=ch, name="Attended RSVP Member")
    AttendanceRecordFactory.create(event=event, user=member, chapter=ch, status="attended", was_active=True)
    client, _ = auto_login_user(user=member)

    response = client.post(event.get_rsvp_url())

    assert response.status_code == 302
    record = AttendanceRecord.objects.get(event=event, user=member)
    assert record.status == AttendanceRecord.STATUS.ATTENDED  # not downgraded


# ===========================================================================
# WI-6 privacy — no cross-chapter roster exposure
# ===========================================================================


@pytest.mark.django_db
def test_event_detail_roster_hidden_cross_chapter(auto_login_user, chapter_factory):
    ch_host, ch_other = _chapters(chapter_factory, 2)
    event = _event(ch_host, "Private Roster Event", is_public=True, approval_status="approved")
    attendee = UserFactory.create(chapter=ch_host, name="Roster Attendee Secret")
    AttendanceRecordFactory.create(event=event, user=attendee, chapter=ch_host, status="signed_up", was_active=True)
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch_other, name="Cross Chapter Viewer"))

    response = client.get(event.get_absolute_url())

    assert response.status_code == 200
    assert response.context["can_view_attendance"] is False
    assert reverse("users:profile", kwargs={"username": attendee.username}).encode() not in response.content


@pytest.mark.django_db
def test_event_detail_roster_visible_same_chapter(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Own Roster Event", is_public=True, approval_status="approved")
    attendee = UserFactory.create(chapter=ch, name="Own Roster Attendee")
    AttendanceRecordFactory.create(event=event, user=attendee, chapter=ch, status="attended", was_active=True)
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch, name="Same Chapter Viewer"))

    response = client.get(event.get_absolute_url())

    assert response.status_code == 200
    assert response.context["can_view_attendance"] is True
    assert reverse("users:profile", kwargs={"username": attendee.username}).encode() in response.content


# ===========================================================================
# Chapter detail — upcoming public events table
# ===========================================================================


@pytest.mark.django_db
def test_chapter_detail_shows_upcoming_public_events(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    _event(ch, "Chapter Public Upcoming", is_public=True, approval_status="approved")
    _event(ch, "Chapter Public Past", date=PAST, is_public=True, approval_status="approved")
    _event(ch, "Chapter Private Event", is_public=False, approval_status="approved")
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch, name="Chapter Detail Viewer"))

    response = client.get(reverse("chapters:detail", kwargs={"slug": ch.slug}))

    assert response.status_code == 200
    names = [e.name for e in response.context["public_events"]]
    assert "Chapter Public Upcoming" in names
    assert "Chapter Public Past" not in names  # past excluded
    assert "Chapter Private Event" not in names  # non-public excluded


# ===========================================================================
# Follow-up: regular own-chapter events, Un-RSVP, RSVP from the events table
# ===========================================================================


@pytest.mark.django_db
def test_calendar_shows_regular_chapter_event_and_allows_rsvp(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Regular Chapter Event")  # own chapter, NOT public
    member = UserFactory.create(chapter=ch, name="Regular Cal Member")
    client, _ = auto_login_user(user=member)

    response = client.get(_cal_url(month=_month(FUTURE)))

    assert response.status_code == 200
    shown = {e.pk: e for e in response.context["events"]}
    assert event.pk in shown
    assert shown[event.pk].member_can_rsvp is True

    rsvp = client.post(event.get_rsvp_url())
    assert rsvp.status_code == 302
    assert AttendanceRecord.objects.filter(event=event, user=member, status="signed_up").exists()


@pytest.mark.django_db
def test_calendar_shows_cancel_rsvp_after_signup(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Cancel Cal Event", is_public=True, approval_status="approved")
    member = UserFactory.create(chapter=ch, name="Cancel Cal Member")
    client, _ = auto_login_user(user=member)
    client.post(event.get_rsvp_url())

    response = client.get(_cal_url(month=_month(FUTURE)))

    assert response.status_code == 200
    assert b"Cancel RSVP" in response.content


@pytest.mark.django_db
def test_un_rsvp_removes_signed_up_record(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Un RSVP Event", is_public=True, approval_status="approved")
    member = UserFactory.create(chapter=ch, name="Un RSVP Member")
    client, _ = auto_login_user(user=member)
    client.post(event.get_rsvp_url())
    assert AttendanceRecord.objects.filter(event=event, user=member, status="signed_up").exists()

    response = client.post(event.get_rsvp_url(), {"action": "cancel"})

    assert response.status_code == 302
    assert not AttendanceRecord.objects.filter(event=event, user=member).exists()


@pytest.mark.django_db
def test_un_rsvp_does_not_remove_attended(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Attended No Cancel Event", is_public=True, approval_status="approved")
    member = UserFactory.create(chapter=ch, name="Attended No Cancel Member")
    AttendanceRecordFactory.create(event=event, user=member, chapter=ch, status="attended", was_active=True)
    client, _ = auto_login_user(user=member)

    response = client.post(event.get_rsvp_url(), {"action": "cancel"})

    assert response.status_code == 302
    assert AttendanceRecord.objects.get(event=event, user=member).status == "attended"


@pytest.mark.django_db
def test_events_list_offers_rsvp_and_tracks_status(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "List RSVP Event")  # upcoming own-chapter event
    member = UserFactory.create(chapter=ch, name="List RSVP Member")
    client, _ = auto_login_user(user=member)

    response = client.get(reverse("events:list"))

    assert response.status_code == 200
    assert event.get_rsvp_url().encode() in response.content
    assert event.pk not in response.context["my_rsvp_status"]

    client.post(event.get_rsvp_url())
    after = client.get(reverse("events:list"))
    assert after.context["my_rsvp_status"].get(event.pk) == "signed_up"
    # Once signed up the table offers a "Cancel RSVP" instead of a fresh RSVP.
    assert b"Cancel RSVP" in after.content


@pytest.mark.django_db
def test_events_list_columns_reduced(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    _event(ch, "Column Test Event")
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch, name="Column Test Member"))

    response = client.get(reverse("events:list"))

    assert response.status_code == 200
    names = [column.name for column in response.context["table"].columns]
    # Kept columns.
    for kept in ("name", "date", "type", "score", "description", "is_public", "parent_event"):
        assert kept in names
    # Removed stat columns.
    for gone in ("members", "pledges", "alumni", "duration", "stem", "host", "virtual", "miles", "raised"):
        assert gone not in names


@pytest.mark.django_db
def test_own_profile_shows_cancel_rsvp_for_future_signup(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Profile Cancel Event", is_public=True, approval_status="approved")
    member = UserFactory.create(chapter=ch, name="Profile Cancel Member")
    AttendanceRecordFactory.create(event=event, user=member, chapter=ch, status="signed_up", was_active=True)
    client, _ = auto_login_user(user=member)

    response = client.get(reverse("users:profile", kwargs={"username": member.username}))

    assert response.status_code == 200
    assert b"Cancel RSVP" in response.content


@pytest.mark.django_db
def test_other_profile_hides_cancel_rsvp(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    event = _event(ch, "Profile No Cancel Event", is_public=True, approval_status="approved")
    member = UserFactory.create(chapter=ch, name="Profile Owner Member")
    AttendanceRecordFactory.create(event=event, user=member, chapter=ch, status="signed_up", was_active=True)
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch, name="Profile Other Viewer"))

    response = client.get(reverse("users:profile", kwargs={"username": member.username}))

    assert response.status_code == 200
    assert b"Cancel RSVP" not in response.content


@pytest.mark.django_db
def test_calendar_has_month_year_selectors_and_both_views(auto_login_user, chapter_factory):
    ch = chapter_factory.create()
    _event(ch, "Toggle Event", is_public=True, approval_status="approved")
    client, _ = auto_login_user(user=UserFactory.create(chapter=ch, name="Toggle Member"))

    response = client.get(reverse("events:calendar"))

    assert response.status_code == 200
    content = response.content
    # Month / year jump selectors (#3).
    assert b'id="jump-month-select"' in content
    assert b'id="jump-year-select"' in content
    assert response.context["month_choices"]
    assert response.context["year_choices"]
    # "Today" jump button links to the current month.
    assert b">Today</a>" in content
    assert f"month={TODAY.year}-{TODAY.month:02d}".encode() in content
    # Both views rendered so the toggle + remembered preference work client-side (#4/#5).
    assert b'id="calendar-view"' in content
    assert b'id="table-view"' in content
    assert b"eventsCalendarView" in content
    assert b"setEventsView" in content
