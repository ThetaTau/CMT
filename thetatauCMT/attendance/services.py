"""Permission, roster, and record-writing helpers for the attendance module."""

from django.utils import timezone

from .models import AttendanceRecord


def can_record_attendance(user, event):
    """Only the Chapter Scribe / officers of the event's chapter (or National
    Officers / Admins) may record attendance for an event."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_national_officer_group:
        return True
    if event.chapter_id and user.is_chapter_officer_group:
        current = user.current_chapter
        if current is not None and current.pk == event.chapter_id:
            return True
    return False


def active_roster_for_event(event):
    """Active members of the event's chapter as of the event date (snapshot)."""
    from thetatauCMT.users.models import User

    if not event.chapter_id:
        return User.objects.none()
    return event.chapter.get_actives_for_date(event.date).order_by("last_name", "first_name")


def parent_attendee_roster(event):
    """Members who have an attendance record on the parent event (WI-5 default)."""
    from thetatauCMT.users.models import User

    if not event.parent_event_id:
        return User.objects.none()
    user_ids = AttendanceRecord.objects.filter(event_id=event.parent_event_id).values_list("user_id", flat=True)
    return User.objects.filter(pk__in=user_ids).order_by("last_name", "first_name")


def record_attendance(event, member, status, recorded_by, when=None):
    """Create or update ``member``'s attendance for ``event``.

    Snapshots the member's active status (as of the event date), home chapter,
    recorder, and time; logs any status transition. Returns ``(record, created)``.
    """
    when = when or timezone.now()
    was_active = member.is_active_on(event.date)
    try:
        rec = AttendanceRecord.objects.get(event=event, user=member)
        created = False
    except AttendanceRecord.DoesNotExist:
        rec = AttendanceRecord(event=event, user=member, status=status)
        created = True
    old_status = "" if created else rec.status
    rec.was_active = was_active
    rec.chapter = member.chapter
    rec.recorded_by = recorded_by
    rec.recorded_at = when
    if created:
        rec.status = status
        rec.save()
        rec.log_transition("", status, changed_by=recorded_by)
    elif old_status != status:
        rec.previous_status = old_status
        rec.status = status
        rec.transitioned_at = when
        rec.save()
        rec.log_transition(old_status, status, changed_by=recorded_by)
    else:
        rec.save()
    return rec, created
