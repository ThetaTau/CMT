"""WI-8 tests — member attendance view + self-service logging.

Acceptance criteria covered by name:
    * correct events listed (chapter + national + sub-events)
    * national events highlighted
    * sub-events shown under/with their parent context
    * permission scoping — any member may VIEW; only the member or a National
      Officer may ADD; events outside the member's scope are rejected
    * autocomplete scoping (national + own chapter, gated to member/natoff)
"""

import datetime
import json

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.attendance.models import AttendanceRecord
from thetatauCMT.attendance.tests.factories import AttendanceRecordFactory
from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.tests.factories import UserFactory

EVENT_DATE = datetime.date(2026, 6, 1)


def _evt_score_type():
    return ScoreType.objects.filter(type="Evt").first()


def _chapter_event(chapter, name, **kwargs):
    return EventFactory.create(chapter=chapter, type=_evt_score_type(), date=EVENT_DATE, name=name, **kwargs)


def _national_event(name, **kwargs):
    return EventFactory.create(
        chapter=None, is_national=True, type=_evt_score_type(), date=EVENT_DATE, name=name, **kwargs
    )


def _attend(event, member, status=AttendanceRecord.STATUS.ATTENDED):
    return AttendanceRecordFactory.create(event=event, user=member, chapter=member.chapter, status=status)


def _natoff(chapter):
    user = UserFactory.create(chapter=chapter)
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    return user


def _distinct_chapter(chapter_factory, other_than):
    for value in GREEK_ABR.values():
        if value != other_than.name:
            return chapter_factory.create(name=value)
    return chapter_factory.create()


def _profile_url(member):
    return reverse("users:profile", kwargs={"username": member.username})


def _add_url(member):
    return reverse("attendance:member_add", kwargs={"username": member.username})


# ===========================================================================
# Table content — correct events listed
# ===========================================================================


@pytest.mark.django_db
def test_member_profile_lists_attended_events(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Attend Target One")
    e1 = _chapter_event(chapter, "Alpha Mixer")
    e2 = _chapter_event(chapter, "Beta Service")
    _attend(e1, member)
    _attend(e2, member)
    viewer = UserFactory.create(name="Viewer One")
    client, _ = auto_login_user(user=viewer)

    response = client.get(_profile_url(member))

    assert response.status_code == 200
    assert b"Alpha Mixer" in response.content
    assert b"Beta Service" in response.content
    assert {r.event_id for r in response.context["attendance_records"]} == {e1.pk, e2.pk}


@pytest.mark.django_db
def test_national_event_highlighted(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Attend Target Nat")
    nat = _national_event("National Summit")
    _attend(nat, member)
    viewer = UserFactory.create(name="Viewer Nat")
    client, _ = auto_login_user(user=viewer)

    response = client.get(_profile_url(member))

    assert response.status_code == 200
    assert b"National Summit" in response.content
    # National attendance rows carry the highlight class + a National badge.
    assert b"national-attendance" in response.content


@pytest.mark.django_db
def test_chapter_only_event_not_highlighted(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Attend Target Chap")
    _attend(_chapter_event(chapter, "Just A Chapter Event"), member)
    viewer = UserFactory.create(name="Viewer Chap")
    client, _ = auto_login_user(user=viewer)

    response = client.get(_profile_url(member))

    assert response.status_code == 200
    assert b"Just A Chapter Event" in response.content
    assert b"national-attendance" not in response.content


@pytest.mark.django_db
def test_sub_event_shows_parent_context(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Attend Target Sub")
    parent = _chapter_event(chapter, "Parent Conference")
    sub = _chapter_event(chapter, "Breakout Session", parent_event=parent)
    _attend(sub, member)
    viewer = UserFactory.create(name="Viewer Sub")
    client, _ = auto_login_user(user=viewer)

    response = client.get(_profile_url(member))

    assert response.status_code == 200
    assert b"Breakout Session" in response.content
    assert b"Sub-event of" in response.content
    assert b"Parent Conference" in response.content


# ===========================================================================
# Permission scoping — viewing
# ===========================================================================


@pytest.mark.django_db
def test_any_member_can_view_other_members_attendance(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Target Cross")
    _attend(_chapter_event(chapter, "Cross View Event"), member)
    viewer = UserFactory.create(name="Viewer Cross")  # different member, not natoff
    client, _ = auto_login_user(user=viewer)

    response = client.get(_profile_url(member))

    assert response.status_code == 200
    assert b"Cross View Event" in response.content
    # A non-owner, non-officer viewer is not offered the add form.
    assert response.context["can_add_attendance"] is False


@pytest.mark.django_db
def test_owner_sees_add_attendance_form(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Form Owner")
    client, _ = auto_login_user(user=member)

    response = client.get(_profile_url(member))

    assert response.status_code == 200
    assert response.context["can_add_attendance"] is True
    assert b"Log missing attendance" in response.content


# ===========================================================================
# Permission scoping — adding
# ===========================================================================


@pytest.mark.django_db
def test_member_can_add_own_attendance(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Self Logger")
    nat = _national_event("Self Log Summit")
    client, _ = auto_login_user(user=member)

    response = client.post(_add_url(member), {"event": nat.pk, "status": "attended"})

    assert response.status_code == 302
    rec = AttendanceRecord.objects.get(event=nat, user=member)
    assert rec.status == "attended"
    assert rec.recorded_by_id == member.pk


@pytest.mark.django_db
def test_member_can_add_own_chapter_event_attendance(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Self Chap Logger")
    event = _chapter_event(chapter, "My Chapter Retreat")
    client, _ = auto_login_user(user=member)

    response = client.post(_add_url(member), {"event": event.pk, "status": "signed_up"})

    assert response.status_code == 302
    assert AttendanceRecord.objects.filter(event=event, user=member, status="signed_up").exists()


@pytest.mark.django_db
def test_national_officer_can_add_attendance_for_member(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Logged By Nat")
    nat_event = _national_event("Officer Logged Summit")
    natoff = _natoff(chapter)
    client, _ = auto_login_user(user=natoff)

    response = client.post(_add_url(member), {"event": nat_event.pk, "status": "attended"})

    assert response.status_code == 302
    assert AttendanceRecord.objects.filter(event=nat_event, user=member).exists()


@pytest.mark.django_db
def test_non_owner_non_natoff_cannot_add_attendance(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Protected Member")
    nat = _national_event("Denied Summit")
    other = UserFactory.create(chapter=chapter, name="Sneaky Member")
    client, _ = auto_login_user(user=other)

    response = client.post(_add_url(member), {"event": nat.pk, "status": "attended"})

    assert response.status_code == 302
    assert not AttendanceRecord.objects.filter(event=nat, user=member).exists()


@pytest.mark.django_db
def test_cannot_log_event_outside_member_scope(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Scoped Member")
    other_chapter = _distinct_chapter(chapter_factory, chapter)
    foreign_event = _chapter_event(other_chapter, "Foreign Event")
    client, _ = auto_login_user(user=member)

    response = client.post(_add_url(member), {"event": foreign_event.pk, "status": "attended"})

    assert response.status_code == 302
    assert not AttendanceRecord.objects.filter(event=foreign_event, user=member).exists()


# ===========================================================================
# Autocomplete scoping
# ===========================================================================


@pytest.mark.django_db
def test_member_event_autocomplete_scopes_to_national_and_chapter(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="AC Member")
    own = _chapter_event(chapter, "Own Chapter Party")
    nat = _national_event("Autocomplete Summit")
    other_chapter = _distinct_chapter(chapter_factory, chapter)
    foreign = _chapter_event(other_chapter, "Foreign Party")
    client, _ = auto_login_user(user=member)

    response = client.get(
        reverse("attendance:member-event-autocomplete"),
        {"forward": json.dumps({"member_pk": member.pk}), "q": ""},
    )

    assert response.status_code == 200
    ids = {int(r["id"]) for r in response.json()["results"]}
    assert own.pk in ids
    assert nat.pk in ids
    assert foreign.pk not in ids


@pytest.mark.django_db
def test_member_event_autocomplete_denied_for_other_member(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="AC Protected")
    _national_event("Denied AC Summit")
    other = UserFactory.create(chapter=chapter, name="AC Sneaky")
    client, _ = auto_login_user(user=other)

    response = client.get(
        reverse("attendance:member-event-autocomplete"),
        {"forward": json.dumps({"member_pk": member.pk}), "q": ""},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []


# ===========================================================================
# Table links, filters/sorting, and event-detail rollup (UX round)
# ===========================================================================


@pytest.mark.django_db
def test_profile_attendance_links_chapter_to_detail(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Chapter Link Target")
    _attend(_chapter_event(chapter, "Linkable Event"), member)
    client, _ = auto_login_user(user=UserFactory.create(name="Chapter Link Viewer"))

    response = client.get(_profile_url(member))

    assert response.status_code == 200
    assert reverse("chapters:detail", kwargs={"slug": chapter.slug}).encode() in response.content


@pytest.mark.django_db
def test_profile_attendance_has_filter_and_sort_controls(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    member = UserFactory.create(chapter=chapter, name="Filter Target")
    _attend(_chapter_event(chapter, "Filterable Event"), member)
    client, _ = auto_login_user(user=UserFactory.create(name="Filter Viewer"))

    response = client.get(_profile_url(member))

    assert response.status_code == 200
    content = response.content
    assert b'id="attendance-table"' in content
    assert b'id="att-filter-period"' in content
    assert b'id="att-filter-chapter"' in content
    assert b'id="att-filter-name"' in content
    assert b"att-sortable" in content
    assert b"data-periods" in content


@pytest.mark.django_db
def test_event_detail_attendance_links_member_and_chapter(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    event = _chapter_event(chapter, "Detail Link Event")
    member = UserFactory.create(chapter=chapter, name="Detail Attendee")
    _attend(event, member)
    client, _ = auto_login_user(user=UserFactory.create(name="Detail Viewer"))

    response = client.get(event.get_absolute_url())

    assert response.status_code == 200
    assert reverse("users:profile", kwargs={"username": member.username}).encode() in response.content
    assert reverse("chapters:detail", kwargs={"slug": chapter.slug}).encode() in response.content


@pytest.mark.django_db
def test_event_detail_shows_rollup_link_for_parent(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    parent = _chapter_event(chapter, "Rollup Parent")
    _chapter_event(chapter, "Rollup Child", parent_event=parent)
    natoff = _natoff(chapter)
    client, _ = auto_login_user(user=natoff)

    response = client.get(parent.get_absolute_url())

    assert response.status_code == 200
    assert parent.get_attendance_rollup_url().encode() in response.content


@pytest.mark.django_db
def test_event_detail_no_rollup_link_without_sub_events(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    event = _chapter_event(chapter, "No Rollup Event")
    natoff = _natoff(chapter)
    client, _ = auto_login_user(user=natoff)

    response = client.get(event.get_absolute_url())

    assert response.status_code == 200
    assert event.get_attendance_rollup_url().encode() not in response.content
