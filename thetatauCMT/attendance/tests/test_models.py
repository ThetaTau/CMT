import datetime

import pytest
from django.test import override_settings

from thetatauCMT.attendance.models import AttendanceRecord
from thetatauCMT.attendance.quorum import compute_quorum, quorum_status
from thetatauCMT.attendance.services import record_attendance
from thetatauCMT.attendance.tests.factories import AttendanceRecordFactory
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.tests.factories import UserFactory, UserStatusChangeFactory

EVENT_DATE = datetime.date(2026, 6, 1)


def _evt_score_type():
    return ScoreType.objects.filter(type="Evt").first()


def _event(chapter, date=EVENT_DATE, **kwargs):
    return EventFactory.create(chapter=chapter, type=_evt_score_type(), date=date, **kwargs)


def _active_member(chapter, date=EVENT_DATE, **kwargs):
    user = UserFactory.create(chapter=chapter, **kwargs)
    UserStatusChangeFactory.create(
        user=user,
        status="active",
        start=date - datetime.timedelta(days=30),
        end=date + datetime.timedelta(days=30),
    )
    return user


# ===========================================================================
# Quorum (WI-3) — configurable rule + met/not-met boundary
# ===========================================================================


def test_quorum_majority_default():
    assert compute_quorum(10) == 6
    assert compute_quorum(11) == 6
    assert compute_quorum(1) == 1
    assert compute_quorum(0) == 0


def test_quorum_met_not_met_boundary():
    # 10 active -> need 6
    not_met = quorum_status(10, 5)
    met = quorum_status(10, 6)
    assert not_met["required"] == 6
    assert not_met["met"] is False
    assert met["met"] is True


@override_settings(ATTENDANCE_QUORUM_RULE="two_thirds")
def test_quorum_rule_configurable_two_thirds():
    assert compute_quorum(9) == 6  # ceil(9 * 2/3)


@override_settings(ATTENDANCE_QUORUM_RULE="0.75")
def test_quorum_rule_configurable_fraction():
    assert compute_quorum(8) == 6  # ceil(8 * 0.75)


# ===========================================================================
# Snapshot values (WI-3)
# ===========================================================================


@pytest.mark.django_db
def test_snapshot_values_stored_correctly(chapter_factory, user_factory):
    chapter = chapter_factory.create()
    event = _event(chapter)
    member = _active_member(chapter)
    recorder = user_factory.create(chapter=chapter)
    rec, created = record_attendance(event, member, AttendanceRecord.STATUS.ATTENDED, recorder)
    assert created is True
    assert rec.status == AttendanceRecord.STATUS.ATTENDED
    assert rec.was_active is True
    assert rec.chapter_id == member.chapter_id
    assert rec.recorded_by_id == recorder.pk
    assert rec.recorded_at is not None


@pytest.mark.django_db
def test_was_active_false_for_inactive_member(chapter_factory, user_factory):
    chapter = chapter_factory.create()
    event = _event(chapter)
    inactive = user_factory.create(chapter=chapter)  # no active status change
    recorder = user_factory.create(chapter=chapter)
    rec, _ = record_attendance(event, inactive, AttendanceRecord.STATUS.ATTENDED, recorder)
    assert rec.was_active is False
    assert inactive.is_active_on(event.date) is False


# ===========================================================================
# WI-4 — states, transitions, history preservation
# ===========================================================================


@pytest.mark.django_db
def test_set_status_logs_transition_and_preserves_history(chapter_factory, user_factory):
    chapter = chapter_factory.create()
    event = _event(chapter)
    member = _active_member(chapter)
    recorder = user_factory.create(chapter=chapter)
    rec, _ = record_attendance(event, member, AttendanceRecord.STATUS.SIGNED_UP, recorder)
    # Initial creation logs a transition.
    assert rec.transitions.filter(to_status="signed_up").exists()
    rec.set_status(AttendanceRecord.STATUS.ATTENDED, changed_by=recorder)
    rec.refresh_from_db()
    assert rec.status == AttendanceRecord.STATUS.ATTENDED
    assert rec.previous_status == AttendanceRecord.STATUS.SIGNED_UP
    # History preserved: the sign-up record is not deleted; transition logged.
    assert AttendanceRecord.objects.filter(pk=rec.pk).exists()
    assert rec.transitions.filter(from_status="signed_up", to_status="attended").exists()


@pytest.mark.django_db
def test_set_status_noop_when_unchanged(chapter_factory, user_factory):
    chapter = chapter_factory.create()
    event = _event(chapter)
    member = _active_member(chapter)
    recorder = user_factory.create(chapter=chapter)
    rec, _ = record_attendance(event, member, AttendanceRecord.STATUS.ATTENDED, recorder)
    before = rec.transitions.count()
    rec.set_status(AttendanceRecord.STATUS.ATTENDED, changed_by=recorder)
    assert rec.transitions.count() == before  # no new transition for a no-op


@pytest.mark.django_db
def test_is_guest_property(chapter_factory):
    home = chapter_factory.create()
    event_chapter = chapter_factory.create()
    event = _event(event_chapter)
    guest = _active_member(home)
    rec = AttendanceRecordFactory.create(event=event, user=guest, chapter=home)
    assert rec.is_guest is True
    local = _active_member(event_chapter)
    local_rec = AttendanceRecordFactory.create(event=event, user=local, chapter=event_chapter)
    assert local_rec.is_guest is False
