"""WI-9 tests — regional & national events + attendance dashboard.

Acceptance criteria covered by name:
    * percentage math per chapter (attended active / active on roster, snapshots)
    * only national events selectable for the breakdown
    * correct handling of chapters with zero attendance (incl. 0 active → no /0)
plus top-attended aggregation (national + region scope) and permission scoping.
"""

import datetime

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.attendance.forms import NationalEventLookupForm
from thetatauCMT.attendance.services import national_event_chapter_breakdown, top_attended_events
from thetatauCMT.attendance.tests.factories import AttendanceRecordFactory
from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.tests.factories import UserFactory

EVENT_DATE = datetime.date(2026, 6, 1)


def _evt_score_type():
    return ScoreType.objects.filter(type="Evt").first()


def _national_event(name, **kwargs):
    return EventFactory.create(
        chapter=None, is_national=True, type=_evt_score_type(), date=EVENT_DATE, name=name, **kwargs
    )


def _chapter_event(chapter, name, **kwargs):
    return EventFactory.create(chapter=chapter, type=_evt_score_type(), date=EVENT_DATE, name=name, **kwargs)


def _distinct_chapter(chapter_factory, other_than):
    for value in GREEK_ABR.values():
        if value != other_than.name:
            return chapter_factory.create(name=value)
    return chapter_factory.create()


def _record(event, chapter, was_active, status):
    member = UserFactory.create(chapter=chapter)
    return AttendanceRecordFactory.create(event=event, user=member, was_active=was_active, status=status)


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


# ===========================================================================
# Percentage math per chapter (snapshot values)
# ===========================================================================


@pytest.mark.django_db
def test_chapter_breakdown_percentage_math(chapter_factory):
    chapter = chapter_factory.create()
    event = _national_event("Math Summit")
    _record(event, chapter, was_active=True, status="attended")
    _record(event, chapter, was_active=True, status="attended")
    _record(event, chapter, was_active=True, status="signed_up")

    breakdown = national_event_chapter_breakdown(event)

    assert len(breakdown) == 1
    row = breakdown[0]
    assert row["chapter_id"] == chapter.pk
    assert row["attended_active"] == 2
    assert row["active_on_roster"] == 3
    assert row["percentage"] == 66.7  # round(2/3*100, 1)


@pytest.mark.django_db
def test_chapter_breakdown_groups_multiple_chapters(chapter_factory):
    event = _national_event("Multi Summit")
    ch_a = chapter_factory.create()
    ch_b = _distinct_chapter(chapter_factory, ch_a)
    _record(event, ch_a, was_active=True, status="attended")
    _record(event, ch_a, was_active=True, status="no_show")
    _record(event, ch_b, was_active=True, status="attended")

    breakdown = {row["chapter_id"]: row for row in national_event_chapter_breakdown(event)}

    assert breakdown[ch_a.pk]["attended_active"] == 1
    assert breakdown[ch_a.pk]["active_on_roster"] == 2
    assert breakdown[ch_a.pk]["percentage"] == 50.0
    assert breakdown[ch_b.pk]["attended_active"] == 1
    assert breakdown[ch_b.pk]["active_on_roster"] == 1
    assert breakdown[ch_b.pk]["percentage"] == 100.0


# ===========================================================================
# Zero-attendance handling
# ===========================================================================


@pytest.mark.django_db
def test_chapter_breakdown_zero_attended_is_zero_percent(chapter_factory):
    chapter = chapter_factory.create()
    event = _national_event("Zero Summit")
    _record(event, chapter, was_active=True, status="signed_up")
    _record(event, chapter, was_active=True, status="no_show")

    row = national_event_chapter_breakdown(event)[0]

    assert row["attended_active"] == 0
    assert row["active_on_roster"] == 2
    assert row["percentage"] == 0.0


@pytest.mark.django_db
def test_chapter_breakdown_no_active_members_no_divide_by_zero(chapter_factory):
    chapter = chapter_factory.create()
    event = _national_event("Inactive Summit")
    _record(event, chapter, was_active=False, status="attended")
    _record(event, chapter, was_active=False, status="attended")

    row = national_event_chapter_breakdown(event)[0]

    assert row["active_on_roster"] == 0
    assert row["attended_active"] == 0
    assert row["percentage"] == 0.0  # no ZeroDivisionError
    assert row["total_records"] == 2


@pytest.mark.django_db
def test_chapter_breakdown_empty_for_event_without_attendance():
    event = _national_event("Empty Summit")
    assert national_event_chapter_breakdown(event) == []


# ===========================================================================
# Top attended events aggregation
# ===========================================================================


@pytest.mark.django_db
def test_top_attended_events_national_orders_by_attendance(chapter_factory):
    chapter = chapter_factory.create()
    low = _national_event("Low Attendance")
    high = _national_event("High Attendance")
    _record(low, chapter, was_active=True, status="attended")
    for _ in range(3):
        _record(high, chapter, was_active=True, status="attended")

    events = list(top_attended_events(scope="national"))
    names = [e.name for e in events]

    assert names.index("High Attendance") < names.index("Low Attendance")
    top = next(e for e in events if e.name == "High Attendance")
    assert top.attended_count == 3


@pytest.mark.django_db
def test_top_attended_events_excludes_events_without_attendance():
    _national_event("No Attendance Event")
    assert "No Attendance Event" not in [e.name for e in top_attended_events(scope="national")]


@pytest.mark.django_db
def test_top_attended_events_region_scope_excludes_national(chapter_factory):
    region = RegionFactory.create(name="Testregion Nine")
    chapter = chapter_factory.create(region=region)
    region_event = _chapter_event(chapter, "Region Scoped Event")
    _record(region_event, chapter, was_active=True, status="attended")
    national_event = _national_event("National Not In Region")
    _record(national_event, chapter, was_active=True, status="attended")

    names = [e.name for e in top_attended_events(scope=region.slug)]

    assert "Region Scoped Event" in names
    assert "National Not In Region" not in names


# ===========================================================================
# Only national events selectable (form level)
# ===========================================================================


@pytest.mark.django_db
def test_lookup_form_rejects_non_national_event(chapter_factory):
    chapter = chapter_factory.create()
    chapter_event = _chapter_event(chapter, "Chapter Only Event")

    form = NationalEventLookupForm({"event": chapter_event.pk})

    assert not form.is_valid()


@pytest.mark.django_db
def test_lookup_form_accepts_national_event():
    national_event = _national_event("Selectable National Event")

    form = NationalEventLookupForm({"event": national_event.pk})

    assert form.is_valid()
    assert form.cleaned_data["event"].pk == national_event.pk


# ===========================================================================
# Dashboard view — permission + rendering
# ===========================================================================


@pytest.mark.django_db
def test_dashboard_requires_natoff(auto_login_user):
    client, _ = auto_login_user()  # regular member
    response = client.get(reverse("regions:event_attendance"))
    assert response.status_code == 302


@pytest.mark.django_db
def test_dashboard_accessible_to_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    response = client.get(reverse("regions:event_attendance"))
    assert response.status_code == 200
    assert response.context["scope"] == "national"


@pytest.mark.django_db
def test_dashboard_shows_top_events_with_links(auto_login_user, chapter_factory):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    event = _national_event("Dashboard Top Event")
    chapter = chapter_factory.create()
    _record(event, chapter, was_active=True, status="attended")

    response = client.get(reverse("regions:event_attendance"))

    assert response.status_code == 200
    assert b"Dashboard Top Event" in response.content
    assert event.get_absolute_url().encode() in response.content


@pytest.mark.django_db
def test_dashboard_breakdown_for_national_event(auto_login_user, chapter_factory):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    event = _national_event("Breakdown Event")
    chapter = chapter_factory.create()
    _record(event, chapter, was_active=True, status="attended")
    _record(event, chapter, was_active=True, status="signed_up")

    response = client.get(reverse("regions:event_attendance"), {"event": event.pk})

    assert response.status_code == 200
    assert response.context["breakdown_event"].pk == event.pk
    breakdown = response.context["chapter_breakdown"]
    assert len(breakdown) == 1
    assert breakdown[0]["percentage"] == 50.0


@pytest.mark.django_db
def test_dashboard_ignores_non_national_event_for_breakdown(auto_login_user, chapter_factory):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    chapter = chapter_factory.create()
    chapter_event = _chapter_event(chapter, "Chapter Only Breakdown")

    response = client.get(reverse("regions:event_attendance"), {"event": chapter_event.pk})

    assert response.status_code == 200
    assert "breakdown_event" not in response.context
