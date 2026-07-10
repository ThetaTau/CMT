"""WI-7 tests — national event bulk attendance upload + matching.

One test per named acceptance criterion:
    * exact-email auto-match
    * name + grad-year + chapter > 60% auto-match
    * < 60% routes to the manual queue
    * admin manual resolution creates an AttendanceRecord
    * idempotent re-upload
    * permission gating (upload + resolve restricted to National Officers)
plus id/badge tier and matcher-scoring unit coverage.
"""

import datetime

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.attendance.matching import get_threshold, match_row
from thetatauCMT.attendance.models import AttendanceRecord, MatchQueueItem
from thetatauCMT.attendance.upload import ingest_attendance_csv, parse_rows, row_fingerprint
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.tests.factories import UserFactory

EVENT_DATE = datetime.date(2026, 6, 1)


def _evt_score_type():
    return ScoreType.objects.filter(type="Evt").first()


def _national_event(**kwargs):
    kwargs.setdefault("name", "Nat Conclave")
    return EventFactory.create(chapter=None, is_national=True, type=_evt_score_type(), date=EVENT_DATE, **kwargs)


def _natoff():
    """A National Officer (natoff group) — used as uploader/resolver."""
    user = UserFactory.create()
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    return user


def _login_natoff(auto_login_user):
    user = _natoff()
    client, _ = auto_login_user(user=user)
    return client, user


def _member(chapter, **kwargs):
    return UserFactory.create(chapter=chapter, **kwargs)


# ===========================================================================
# Auto-match tiers
# ===========================================================================


@pytest.mark.django_db
def test_exact_email_auto_match(chapter_factory):
    """A row with only an exact email auto-matches and records attendance."""
    event = _national_event()
    chapter = chapter_factory.create()
    natoff = _natoff()
    member = _member(chapter, name="Ada Lovelace", first_name="Ada", last_name="Lovelace", email="ada@example.com")

    result = ingest_attendance_csv(event, b"email\nada@example.com\n", natoff)

    assert result.auto_matched == 1
    assert result.queued == 0
    rec = AttendanceRecord.objects.get(event=event, user=member)
    assert rec.status == AttendanceRecord.STATUS.ATTENDED
    # Attendance snapshots the member's HOME chapter (national event has none).
    assert rec.chapter_id == chapter.pk


@pytest.mark.django_db
def test_name_grad_year_chapter_over_60_auto_match(chapter_factory):
    """Name + graduation year + chapter agreement pushes confidence over 60%."""
    event = _national_event()
    chapter = chapter_factory.create()
    natoff = _natoff()
    member = _member(
        chapter,
        name="Gwendolyn Trask",
        first_name="Gwendolyn",
        last_name="Trask",
        graduation_year=1988,
    )

    csv = f"name,chapter,graduation_year\nGwendolyn Trask,{chapter.name},1988\n".encode()
    result = ingest_attendance_csv(event, csv, natoff)

    assert result.auto_matched == 1, result.as_dict()
    assert AttendanceRecord.objects.filter(event=event, user=member).exists()


@pytest.mark.django_db
def test_member_id_auto_match(chapter_factory):
    """Tier 1: an explicit member id (pk) auto-matches."""
    event = _national_event()
    chapter = chapter_factory.create()
    natoff = _natoff()
    member = _member(chapter, name="Id Tier Member", first_name="Id", last_name="Member")

    result = ingest_attendance_csv(event, f"member_id\n{member.pk}\n".encode(), natoff)

    assert result.auto_matched == 1
    assert AttendanceRecord.objects.filter(event=event, user=member).exists()


@pytest.mark.django_db
def test_badge_number_auto_match(chapter_factory):
    """Tier 1: a badge number is treated as an exact id-style match."""
    event = _national_event()
    chapter = chapter_factory.create()
    natoff = _natoff()
    member = _member(chapter, name="Badge Tier Member", first_name="Badge", last_name="Member", badge_number=770123)

    result = ingest_attendance_csv(event, b"badge\n770123\n", natoff)

    assert result.auto_matched == 1
    assert AttendanceRecord.objects.filter(event=event, user=member).exists()


# ===========================================================================
# Low-confidence routing to the manual queue
# ===========================================================================


@pytest.mark.django_db
def test_low_confidence_routes_to_queue(chapter_factory):
    """A weak, name-only partial match stays below threshold and is queued."""
    event = _national_event()
    chapter = chapter_factory.create()
    natoff = _natoff()
    member = _member(
        chapter,
        name="Zylphia Quillfeather",
        first_name="Zylphia",
        last_name="Quillfeather",
    )

    # First name only -> similarity well below the 0.60 auto-accept threshold.
    result = ingest_attendance_csv(event, b"name\nZylphia\n", natoff)

    assert result.auto_matched == 0
    assert result.queued == 1
    assert not AttendanceRecord.objects.filter(event=event).exists()
    item = MatchQueueItem.objects.get(event=event)
    assert item.status == MatchQueueItem.Status.PENDING
    assert item.raw_name == "Zylphia"
    assert item.best_score <= get_threshold()
    # The real member is still surfaced as a candidate for the admin to confirm.
    assert any(c["user_id"] == member.pk for c in item.candidates)


@pytest.mark.django_db
def test_row_without_identity_is_skipped(chapter_factory):
    """A row with no id/email/name is skipped, not queued."""
    event = _national_event()
    natoff = _natoff()

    result = ingest_attendance_csv(event, b"chapter,graduation_year\nBeta,2010\n", natoff)

    assert result.queued == 0
    assert result.skipped == 1
    assert MatchQueueItem.objects.filter(event=event).count() == 0


# ===========================================================================
# Admin manual resolution
# ===========================================================================


@pytest.mark.django_db
def test_admin_manual_resolution_creates_attendance_record(auto_login_user, chapter_factory):
    """Resolving a queued row via the admin endpoint creates the AttendanceRecord."""
    event = _national_event()
    chapter = chapter_factory.create()
    client, natoff = _login_natoff(auto_login_user)
    member = _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")
    ingest_attendance_csv(event, b"name\nZylphia\n", natoff)
    item = MatchQueueItem.objects.get(event=event, status=MatchQueueItem.Status.PENDING)

    response = client.post(
        reverse("attendance:match_queue_resolve"),
        {
            "item": item.pk,
            "action": "resolve",
            "user_id": member.pk,
            "status": AttendanceRecord.STATUS.ATTENDED,
            "event": event.pk,
        },
    )

    assert response.status_code == 302
    item.refresh_from_db()
    assert item.status == MatchQueueItem.Status.RESOLVED
    rec = AttendanceRecord.objects.get(event=event, user=member)
    assert rec.status == AttendanceRecord.STATUS.ATTENDED
    assert item.attendance_record_id == rec.pk
    assert item.resolved_by_id == natoff.pk


@pytest.mark.django_db
def test_admin_skip_resolves_without_record(auto_login_user, chapter_factory):
    """Skipping a queued row closes it without creating attendance."""
    event = _national_event()
    chapter = chapter_factory.create()
    client, natoff = _login_natoff(auto_login_user)
    _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")
    ingest_attendance_csv(event, b"name\nZylphia\n", natoff)
    item = MatchQueueItem.objects.get(event=event, status=MatchQueueItem.Status.PENDING)

    response = client.post(
        reverse("attendance:match_queue_resolve"),
        {"item": item.pk, "action": "skip", "event": event.pk},
    )

    assert response.status_code == 302
    item.refresh_from_db()
    assert item.status == MatchQueueItem.Status.SKIPPED
    assert not AttendanceRecord.objects.filter(event=event).exists()


# ===========================================================================
# Idempotent re-uploads
# ===========================================================================


@pytest.mark.django_db
def test_idempotent_reupload_does_not_double_create(chapter_factory):
    """Re-uploading the same file updates (not duplicates) the attendance record."""
    event = _national_event()
    chapter = chapter_factory.create()
    natoff = _natoff()
    member = _member(chapter, name="Ida Rhodes", first_name="Ida", last_name="Rhodes", email="ida@example.com")
    csv = b"email\nida@example.com\n"

    first = ingest_attendance_csv(event, csv, natoff)
    second = ingest_attendance_csv(event, csv, natoff)

    assert first.auto_matched == 1
    assert second.auto_matched == 0
    assert second.updated == 1
    assert AttendanceRecord.objects.filter(event=event, user=member).count() == 1


@pytest.mark.django_db
def test_idempotent_reupload_does_not_duplicate_queue_item(chapter_factory):
    """A re-uploaded unresolved row reuses the existing pending queue item."""
    event = _national_event()
    chapter = chapter_factory.create()
    natoff = _natoff()
    _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")
    csv = b"name\nZylphia\n"

    ingest_attendance_csv(event, csv, natoff)
    ingest_attendance_csv(event, csv, natoff)

    assert MatchQueueItem.objects.filter(event=event, status=MatchQueueItem.Status.PENDING).count() == 1


@pytest.mark.django_db
def test_reupload_after_resolution_is_skipped(auto_login_user, chapter_factory):
    """Once a fingerprint is resolved, re-uploading that row is skipped."""
    event = _national_event()
    chapter = chapter_factory.create()
    client, natoff = _login_natoff(auto_login_user)
    member = _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")
    csv = b"name\nZylphia\n"
    ingest_attendance_csv(event, csv, natoff)
    item = MatchQueueItem.objects.get(event=event, status=MatchQueueItem.Status.PENDING)
    item.resolve_to(member, natoff)

    result = ingest_attendance_csv(event, csv, natoff)

    assert result.queued == 0
    assert result.skipped == 1
    assert MatchQueueItem.objects.filter(event=event, status=MatchQueueItem.Status.PENDING).count() == 0
    assert AttendanceRecord.objects.filter(event=event, user=member).count() == 1


# ===========================================================================
# Permission gating
# ===========================================================================


@pytest.mark.django_db
def test_upload_permission_denied_for_regular_member(auto_login_user, chapter_factory):
    """Non-National-Officers cannot open the upload page."""
    chapter = chapter_factory.create()
    regular = _member(chapter, name="Regular Member Upload")
    client, _ = auto_login_user(user=regular)

    response = client.get(reverse("attendance:national_upload"))

    assert response.status_code == 302
    assert AttendanceRecord.objects.count() == 0


@pytest.mark.django_db
def test_resolve_permission_denied_for_regular_member(auto_login_user, chapter_factory):
    """Non-National-Officers cannot resolve queue items or create attendance."""
    event = _national_event()
    chapter = chapter_factory.create()
    natoff = _natoff()
    member = _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")
    ingest_attendance_csv(event, b"name\nZylphia\n", natoff)
    item = MatchQueueItem.objects.get(event=event, status=MatchQueueItem.Status.PENDING)

    regular = _member(chapter, name="Regular Member Resolve")
    client, _ = auto_login_user(user=regular)
    response = client.post(
        reverse("attendance:match_queue_resolve"),
        {"item": item.pk, "action": "resolve", "user_id": member.pk, "event": event.pk},
    )

    assert response.status_code == 302
    item.refresh_from_db()
    assert item.status == MatchQueueItem.Status.PENDING
    assert not AttendanceRecord.objects.filter(event=event).exists()


@pytest.mark.django_db
def test_upload_page_available_to_natoff(auto_login_user):
    """National Officers can open the upload page."""
    client, _ = _login_natoff(auto_login_user)

    response = client.get(reverse("attendance:national_upload"))

    assert response.status_code == 200


# ===========================================================================
# Parser + matcher unit coverage
# ===========================================================================


def test_parse_rows_maps_header_aliases():
    rows = parse_rows(b"Email Address,Full Name,Grad Year\njo@x.com,Jo Q,2001\n")
    assert len(rows) == 1
    row, original = rows[0]
    assert row["email"] == "jo@x.com"
    assert row["name"] == "Jo Q"
    assert row["graduation_year"] == "2001"
    assert original["Full Name"] == "Jo Q"


def test_row_fingerprint_is_stable_and_identity_sensitive():
    a = row_fingerprint({"email": "A@X.com", "name": "Jo"})
    b = row_fingerprint({"email": "a@x.com", "name": "jo"})
    c = row_fingerprint({"email": "different@x.com", "name": "Jo"})
    assert a == b  # case-insensitive
    assert a != c


@pytest.mark.django_db
def test_match_row_email_tier_is_case_insensitive_and_auto(chapter_factory):
    chapter = chapter_factory.create()
    member = _member(chapter, name="Unit Emailer", first_name="Unit", last_name="Emailer", email="unit@example.com")

    result = match_row({"email": "UNIT@EXAMPLE.COM"})

    assert result.tier == "email"
    assert result.user is not None and result.user.pk == member.pk
    assert result.auto_accept


@pytest.mark.django_db
def test_match_row_name_only_partial_is_below_threshold(chapter_factory):
    chapter = chapter_factory.create()
    _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")

    result = match_row({"name": "Zylphia"})

    assert result.tier == "name"
    assert not result.auto_accept
    assert result.score <= get_threshold()
    assert result.candidates  # candidate is still surfaced for review


# ===========================================================================
# Upload prepopulation + inline national review + safe redirect (UX round)
# ===========================================================================


@pytest.mark.django_db
def test_upload_get_prepopulates_event_from_query(auto_login_user):
    """Navigating to the upload page with ?event=<pk> preselects that event."""
    event = _national_event()
    client, _ = _login_natoff(auto_login_user)

    response = client.get(f"{reverse('attendance:national_upload')}?event={event.pk}")

    assert response.status_code == 200
    assert response.context["form"].initial.get("event") == event.pk


@pytest.mark.django_db
def test_upload_get_ignores_non_national_event(auto_login_user, chapter_factory):
    """A chapter (non-national) event id does not prepopulate the national form."""
    chapter = chapter_factory.create()
    chapter_event = EventFactory.create(chapter=chapter, type=_evt_score_type(), date=EVENT_DATE, name="Chapter Ev")
    client, _ = _login_natoff(auto_login_user)

    response = client.get(f"{reverse('attendance:national_upload')}?event={chapter_event.pk}")

    assert response.status_code == 200
    assert response.context["form"].initial.get("event") is None


@pytest.mark.django_db
def test_national_roster_shows_pending_match_queue(auto_login_user, chapter_factory):
    """A national event's attendance page surfaces pending manual-review rows."""
    event = _national_event()
    chapter = chapter_factory.create()
    client, natoff = _login_natoff(auto_login_user)
    _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")
    ingest_attendance_csv(event, b"name\nZylphia\n", natoff)
    item = MatchQueueItem.objects.get(event=event, status=MatchQueueItem.Status.PENDING)

    response = client.get(event.get_attendance_url())

    assert response.status_code == 200
    assert item.pk in [i.pk for i in response.context["match_queue_items"]]
    assert b"Manual attendance to review" in response.content


@pytest.mark.django_db
def test_resolve_honors_next_redirect_back_to_roster(auto_login_user, chapter_factory):
    """Resolving inline from the attendance page returns there (safe ``next``)."""
    event = _national_event()
    chapter = chapter_factory.create()
    client, natoff = _login_natoff(auto_login_user)
    member = _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")
    ingest_attendance_csv(event, b"name\nZylphia\n", natoff)
    item = MatchQueueItem.objects.get(event=event, status=MatchQueueItem.Status.PENDING)
    next_url = event.get_attendance_url()

    response = client.post(
        reverse("attendance:match_queue_resolve"),
        {"item": item.pk, "action": "resolve", "user_id": member.pk, "next": next_url},
    )

    assert response.status_code == 302
    assert response.url == next_url
    assert AttendanceRecord.objects.filter(event=event, user=member).exists()


@pytest.mark.django_db
def test_resolve_rejects_unsafe_next(auto_login_user, chapter_factory):
    """An off-site ``next`` is ignored; falls back to the match queue."""
    event = _national_event()
    chapter = chapter_factory.create()
    client, natoff = _login_natoff(auto_login_user)
    member = _member(chapter, name="Zylphia Quillfeather", first_name="Zylphia", last_name="Quillfeather")
    ingest_attendance_csv(event, b"name\nZylphia\n", natoff)
    item = MatchQueueItem.objects.get(event=event, status=MatchQueueItem.Status.PENDING)

    response = client.post(
        reverse("attendance:match_queue_resolve"),
        {"item": item.pk, "action": "resolve", "user_id": member.pk, "next": "https://evil.example.com/x"},
    )

    assert response.status_code == 302
    assert "evil.example.com" not in response.url
    assert reverse("attendance:match_queue") in response.url
