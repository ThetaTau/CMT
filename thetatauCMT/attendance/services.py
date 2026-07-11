"""Permission, roster, and record-writing helpers for the attendance module."""

from django.db.models import Count, Q
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


def member_attendance(member):
    """All attendance records for ``member``, newest first, with parent context.

    Used by the member profile page (WI-8). ``event__parent_event`` is
    select-related so sub-events can be shown under/with their parent event, and
    the queryset spans every chapter + national event the member attended.
    """
    return (
        AttendanceRecord.objects.filter(user=member)
        .select_related(
            "event",
            "event__chapter",
            "event__type",
            "event__parent_event",
            "event__parent_event__chapter",
        )
        .order_by("-event__date", "event__parent_event_id", "event__name")
    )


# ===========================================================================
# WI-9 — Regional / national events + attendance dashboard aggregations
# ===========================================================================


def top_attended_events(scope="national", limit=15):
    """Top events by number of ``attended`` records for a dashboard scope (WI-9).

    ``scope`` is one of:
      * ``"national"``          — national (org-wide) events
      * ``"candidate_chapter"`` — events hosted by candidate chapters
      * any Region ``slug``     — events hosted by chapters in that region

    Only events with at least one attendance record are returned, ordered by
    attendance descending (ties broken by most recent date).
    """
    from thetatauCMT.events.models import Event

    if scope == "national":
        qs = Event.objects.filter(is_national=True)
    elif scope == "candidate_chapter":
        qs = Event.objects.filter(chapter__candidate_chapter=True)
    else:
        qs = Event.objects.filter(chapter__region__slug=scope)
    return (
        qs.annotate(
            attended_count=Count(
                "attendance_records",
                filter=Q(attendance_records__status=AttendanceRecord.STATUS.ATTENDED),
            )
        )
        .filter(attended_count__gt=0)
        .select_related("chapter", "region", "type")
        .order_by("-attended_count", "-date")[:limit]
    )


def national_event_chapter_breakdown(event):
    """Per-chapter attendance percentage for ``event`` from snapshot values (WI-9).

    Groups the event's attendance records by the snapshot ``chapter`` (the
    member's home chapter at record time) and, using the ``was_active``
    snapshot, computes for each chapter:

      * ``active_on_roster`` — active members with a record for the event
      * ``attended_active``  — active members whose record is ``attended``
      * ``percentage``       — ``attended_active / active_on_roster`` as a percent
                               (``0`` when a chapter has no active members on the
                               roster, so there is never a divide-by-zero)

    All counts come from the recorded snapshot, preserving historical accuracy.
    """
    rows = (
        AttendanceRecord.objects.filter(event=event)
        .values("chapter", "chapter__name", "chapter__slug")
        .annotate(
            active_on_roster=Count("pk", filter=Q(was_active=True)),
            attended_active=Count(
                "pk",
                filter=Q(was_active=True, status=AttendanceRecord.STATUS.ATTENDED),
            ),
            total_records=Count("pk"),
        )
        .order_by("chapter__name")
    )
    breakdown = []
    for row in rows:
        denominator = row["active_on_roster"]
        numerator = row["attended_active"]
        breakdown.append(
            {
                "chapter_id": row["chapter"],
                "chapter_name": row["chapter__name"],
                "chapter_slug": row["chapter__slug"],
                "attended_active": numerator,
                "active_on_roster": denominator,
                "total_records": row["total_records"],
                "percentage": round(numerator / denominator * 100, 1) if denominator else 0.0,
            }
        )
    return breakdown
