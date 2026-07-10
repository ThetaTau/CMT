import datetime

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.attendance.models import AttendanceRecord
from thetatauCMT.attendance.tests.factories import AttendanceRecordFactory
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.tests.factories import UserFactory, UserStatusChangeFactory

EVENT_DATE = datetime.date(2026, 6, 1)


def _evt_score_type():
    return ScoreType.objects.filter(type="Evt").first()


def _active_member(chapter, date=EVENT_DATE, **kwargs):
    user = UserFactory.create(chapter=chapter, **kwargs)
    UserStatusChangeFactory.create(
        user=user,
        status="active",
        start=date - datetime.timedelta(days=30),
        end=date + datetime.timedelta(days=30),
    )
    return user


def _make_scribe(chapter):
    """A clean chapter officer (Scribe) of ``chapter`` — not a National Officer."""
    user = UserFactory.create(chapter=chapter)
    officer, _ = Group.objects.get_or_create(name="officer")
    natoff, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(officer)
    user.groups.remove(natoff)
    user.current_roles = ["scribe"]
    user.save(update_fields=["current_roles"])
    return user


def _setup(auto_login_user, chapter_factory, count=4, date=EVENT_DATE):
    chapter = chapter_factory.create()
    event = EventFactory.create(chapter=chapter, type=_evt_score_type(), date=date)
    members = [_active_member(chapter, date) for _ in range(count)]
    scribe = _make_scribe(chapter)
    client, _ = auto_login_user(user=scribe)
    return client, scribe, chapter, event, members


def _att_url(event, name):
    """Non-enumerable date + slug attendance URL for ``event``."""
    return reverse(
        f"attendance:{name}",
        kwargs={
            "year": event.date.year,
            "month": event.date.month,
            "day": event.date.day,
            "event_slug": event.slug,
        },
    )


def _save_url(event):
    return _att_url(event, "save")


def _roster_url(event):
    return _att_url(event, "roster")


# ===========================================================================
# WI-3 — roster, bulk save, check-all, quorum, permission
# ===========================================================================


@pytest.mark.django_db
def test_bulk_save_records_all_selected(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=4)
    selected = [m.pk for m in members[:3]]
    response = client.post(_save_url(event), {"attendees": selected, "status": "attended"})
    assert response.status_code == 302
    recorded = AttendanceRecord.objects.filter(event=event, status="attended")
    assert set(recorded.values_list("user_id", flat=True)) == set(selected)
    # Snapshot fields populated on each record.
    rec = recorded.first()
    assert rec.was_active is True
    assert rec.recorded_by_id == scribe.pk
    assert rec.chapter_id == chapter.pk


@pytest.mark.django_db
def test_check_all_selects_all_active_members(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=4)
    # The roster page offers a Check All control and lists every active member.
    roster = client.get(_roster_url(event))
    content = roster.content.decode()
    assert "Check All" in content
    for member in members:
        assert str(member.pk) in content
    # "Check All" then Save == posting every active member id -> all recorded.
    response = client.post(_save_url(event), {"attendees": [m.pk for m in members], "status": "attended"})
    assert response.status_code == 302
    assert AttendanceRecord.objects.filter(event=event, status="attended").count() == len(members)


@pytest.mark.django_db
def test_quorum_calculation_and_boundary_via_roster(auto_login_user, chapter_factory):
    # 4 active members -> majority quorum = 3
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=4)
    client.post(_save_url(event), {"attendees": [members[0].pk, members[1].pk], "status": "attended"})
    resp = client.get(_roster_url(event))
    assert resp.context["quorum"]["active_count"] == 4
    assert resp.context["quorum"]["required"] == 3
    assert resp.context["quorum"]["attended_active"] == 2
    assert resp.context["quorum"]["met"] is False
    # One more attendee reaches the boundary -> quorum met.
    client.post(_save_url(event), {"attendees": [m.pk for m in members[:3]], "status": "attended"})
    resp = client.get(_roster_url(event))
    assert resp.context["quorum"]["attended_active"] == 3
    assert resp.context["quorum"]["met"] is True


@pytest.mark.django_db
def test_only_scribe_officers_can_record(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    event = EventFactory.create(chapter=chapter, type=_evt_score_type(), date=EVENT_DATE)
    member = _active_member(chapter)
    regular = UserFactory.create(chapter=chapter)  # not an officer
    client, _ = auto_login_user(user=regular)
    response = client.post(_save_url(event), {"attendees": [member.pk], "status": "attended"})
    assert response.status_code == 302  # redirected away by the permission mixin
    assert AttendanceRecord.objects.filter(event=event).count() == 0


@pytest.mark.django_db
def test_scribe_can_open_roster(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=2)
    resp = client.get(_roster_url(event))
    assert resp.status_code == 200


# ===========================================================================
# WI-4 — sign-up lifecycle: bulk convert, no-show override, history, permission
# ===========================================================================


@pytest.mark.django_db
def test_signed_up_to_attended_bulk_conversion(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=3)
    client.post(_save_url(event), {"attendees": [m.pk for m in members], "status": "signed_up"})
    assert AttendanceRecord.objects.filter(event=event, status="signed_up").count() == 3
    url = _att_url(event, "bulk_update")
    response = client.post(url, {"convert_all": "1"})
    assert response.status_code == 302
    assert AttendanceRecord.objects.filter(event=event, status="attended").count() == 3
    assert AttendanceRecord.objects.filter(event=event, status="signed_up").count() == 0


@pytest.mark.django_db
def test_individual_no_show_override(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=3)
    client.post(_save_url(event), {"attendees": [m.pk for m in members], "status": "signed_up"})
    url = _att_url(event, "bulk_update")
    client.post(url, {"convert_all": "1", "no_show": [members[0].pk]})
    rec0 = AttendanceRecord.objects.get(event=event, user=members[0])
    assert rec0.status == "no_show"
    assert AttendanceRecord.objects.filter(event=event, status="attended").count() == 2


@pytest.mark.django_db
def test_history_preserved_through_conversion(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=1)
    client.post(_save_url(event), {"attendees": [members[0].pk], "status": "signed_up"})
    url = _att_url(event, "bulk_update")
    client.post(url, {"convert_all": "1"})
    rec = AttendanceRecord.objects.get(event=event, user=members[0])
    assert rec.transitions.filter(from_status="signed_up", to_status="attended").exists()
    assert rec.transitions.filter(to_status="signed_up").exists()  # original sign-up kept


@pytest.mark.django_db
def test_bulk_update_permission_gated(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    event = EventFactory.create(chapter=chapter, type=_evt_score_type(), date=EVENT_DATE)
    member = _active_member(chapter)
    AttendanceRecordFactory.create(event=event, user=member, chapter=chapter, status="signed_up")
    regular = UserFactory.create(chapter=chapter)
    client, _ = auto_login_user(user=regular)
    url = _att_url(event, "bulk_update")
    response = client.post(url, {"convert_all": "1"})
    assert response.status_code == 302
    assert AttendanceRecord.objects.filter(event=event, status="attended").count() == 0


# ===========================================================================
# WI-5 — sub-event attendance: independence, roster scoping, rollup
# ===========================================================================


@pytest.mark.django_db
def test_independent_attendance_per_sub_event(auto_login_user, chapter_factory):
    client, scribe, chapter, parent, members = _setup(auto_login_user, chapter_factory, count=3)
    sub = EventFactory.create(
        chapter=chapter, type=_evt_score_type(), date=EVENT_DATE, parent_event=parent, name="Sub A"
    )
    client.post(_save_url(parent), {"attendees": [members[0].pk], "status": "attended"})
    client.post(_save_url(sub), {"attendees": [members[1].pk, members[2].pk], "status": "attended"})
    parent_ids = set(AttendanceRecord.objects.filter(event=parent, status="attended").values_list("user_id", flat=True))
    sub_ids = set(AttendanceRecord.objects.filter(event=sub, status="attended").values_list("user_id", flat=True))
    assert parent_ids == {members[0].pk}
    assert sub_ids == {members[1].pk, members[2].pk}


@pytest.mark.django_db
def test_sub_event_roster_defaults_to_parent_attendees(auto_login_user, chapter_factory):
    client, scribe, chapter, parent, members = _setup(auto_login_user, chapter_factory, count=3)
    sub = EventFactory.create(
        chapter=chapter, type=_evt_score_type(), date=EVENT_DATE, parent_event=parent, name="Sub B"
    )
    AttendanceRecordFactory.create(event=parent, user=members[0], chapter=chapter, status="attended")
    resp = client.get(_roster_url(sub))
    assert resp.context["roster_source"] == "parent"
    roster_ids = [row["member"].pk for row in resp.context["roster"]]
    assert members[0].pk in roster_ids
    assert members[1].pk not in roster_ids
    # Full active roster is still available via ?roster=full.
    resp_full = client.get(_roster_url(sub) + "?roster=full")
    assert resp_full.context["roster_source"] == "active"
    full_ids = [row["member"].pk for row in resp_full.context["roster"]]
    assert members[1].pk in full_ids


@pytest.mark.django_db
def test_rollup_aggregation_correct(auto_login_user, chapter_factory):
    client, scribe, chapter, parent, members = _setup(auto_login_user, chapter_factory, count=3)
    sub1 = EventFactory.create(
        chapter=chapter, type=_evt_score_type(), date=EVENT_DATE, parent_event=parent, name="Sub 1"
    )
    sub2 = EventFactory.create(
        chapter=chapter, type=_evt_score_type(), date=EVENT_DATE, parent_event=parent, name="Sub 2"
    )
    AttendanceRecordFactory.create(event=sub1, user=members[0], chapter=chapter)
    AttendanceRecordFactory.create(event=sub1, user=members[1], chapter=chapter)
    AttendanceRecordFactory.create(event=sub2, user=members[1], chapter=chapter)  # overlap
    url = _att_url(parent, "rollup")
    resp = client.get(url)
    assert resp.status_code == 200
    agg = resp.context["aggregate"]
    assert agg["sub_event_count"] == 2
    assert agg["unique_attendees"] == 2  # members[0] + members[1]
    assert agg["total_records"] == 3  # sub1: 2, sub2: 1


# ===========================================================================
# WI-6 — privacy-safe cross-chapter guest attendance
# ===========================================================================


def _guest_ac_url():
    return reverse("attendance:guest-autocomplete")


@pytest.mark.django_db
def test_guest_autocomplete_rejects_missing_chapter(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=1)
    response = client.get(_guest_ac_url(), {"q": "test"})
    assert response.status_code == 400
    assert response.json()["results"] == []


@pytest.mark.django_db
def test_guest_autocomplete_enforces_min_query_length(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=1)
    other = chapter_factory.create()
    UserFactory.create(chapter=other, name="Findable Guest")
    response = client.get(_guest_ac_url(), {"chapter": other.pk, "q": "F"})  # 1 char < min 2
    assert response.json()["results"] == []


@pytest.mark.django_db
def test_guest_autocomplete_returns_badge_and_grad_year(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=1)
    other = chapter_factory.create()
    UserFactory.create(chapter=other, name="Findable Guest", badge_number=654321, graduation_year=2019)
    response = client.get(_guest_ac_url(), {"chapter": other.pk, "q": "Findable"})
    results = response.json()["results"]
    assert len(results) >= 1
    result = results[0]
    assert result["badge_number"] == 654321
    assert result["graduation_year"] == 2019
    assert "654321" in result["text"]


@pytest.mark.django_db
def test_guest_autocomplete_scoped_to_selected_chapter_only(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=1)
    other = chapter_factory.create()
    UserFactory.create(chapter=other, name="Zulu Otherchapter")
    UserFactory.create(chapter=chapter, name="Zulu Ownchapter")
    response = client.get(_guest_ac_url(), {"chapter": other.pk, "q": "Zulu"})
    names = [r["name"] for r in response.json()["results"]]
    assert "Zulu Otherchapter" in names
    assert "Zulu Ownchapter" not in names


@pytest.mark.django_db
def test_guest_autocomplete_cannot_enumerate_full_membership(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=1)
    other = chapter_factory.create()
    UserFactory.create(chapter=other, name="Someone Else")
    # A chapter but no query -> empty; an empty query -> empty. No way to list all.
    assert client.get(_guest_ac_url(), {"chapter": other.pk}).json()["results"] == []
    assert client.get(_guest_ac_url(), {"chapter": other.pk, "q": ""}).json()["results"] == []


@pytest.mark.django_db
def test_guest_autocomplete_denied_for_non_officer(auto_login_user, chapter_factory):
    chapter = chapter_factory.create()
    other = chapter_factory.create()
    regular = UserFactory.create(chapter=chapter)
    client, _ = auto_login_user(user=regular)
    response = client.get(_guest_ac_url(), {"chapter": other.pk, "q": "test"})
    assert response.status_code == 403


@pytest.mark.django_db
def test_cross_chapter_guest_attendance_recorded(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=1)
    other = chapter_factory.create()
    guest = _active_member(other, name="Guest Member")
    url = _att_url(event, "guest_add")
    response = client.post(url, {"member": guest.pk, "status": "attended"})
    assert response.status_code == 302
    rec = AttendanceRecord.objects.get(event=event, user=guest)
    assert rec.status == "attended"
    assert rec.chapter_id == other.pk  # snapshot of the guest's home chapter
    assert rec.is_guest is True


@pytest.mark.django_db
def test_guest_add_multiple_members_in_one_request(auto_login_user, chapter_factory):
    client, scribe, chapter, event, members = _setup(auto_login_user, chapter_factory, count=1)
    other = chapter_factory.create()
    g1 = _active_member(other, name="Guest One")
    g2 = _active_member(other, name="Guest Two")
    url = _att_url(event, "guest_add")
    response = client.post(url, {"member": [g1.pk, g2.pk], "status": "attended"})
    assert response.status_code == 302
    assert AttendanceRecord.objects.filter(event=event, user=g1).exists()
    assert AttendanceRecord.objects.filter(event=event, user=g2).exists()
    assert AttendanceRecord.objects.get(event=event, user=g1).chapter_id == other.pk
