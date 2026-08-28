"""Permission, roster, and record-writing helpers for the attendance module."""

from django.db.models import Count, Q
from django.utils import timezone

from .models import AttendanceRecord


def can_record_attendance(user, event):
    """Only the Chapter Scribe / officers of the event's chapter (or National
    Officers / Admins) may record attendance for an event."""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_admin or user.is_national_officer_group:
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

    ``AttendanceRecord`` is unique per ``(event, user)``. ``get_or_create`` keeps
    the create path race-safe: a concurrent double submit (e.g. a double-clicked
    "log attendance") can no longer make the second INSERT violate that
    constraint and 500 — the loser of the race falls through to the update
    branch instead.
    """
    when = when or timezone.now()
    was_active = member.is_active_on(event.date)
    rec, created = AttendanceRecord.objects.get_or_create(
        event=event,
        user=member,
        defaults=dict(
            status=status,
            was_active=was_active,
            chapter=member.chapter,
            recorded_by=recorded_by,
            recorded_at=when,
        ),
    )
    if created:
        rec.log_transition("", status, changed_by=recorded_by)
        return rec, True
    # Existing record — refresh the snapshot and log a status transition only if
    # the status actually changed (preserves the prior get-then-update flow).
    old_status = rec.status
    rec.was_active = was_active
    rec.chapter = member.chapter
    rec.recorded_by = recorded_by
    rec.recorded_at = when
    if old_status != status:
        rec.previous_status = old_status
        rec.status = status
        rec.transitioned_at = when
        rec.save()
        rec.log_transition(old_status, status, changed_by=recorded_by)
    else:
        rec.save()
    return rec, False


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


def can_rsvp(user, event):
    """Whether ``user`` may RSVP (sign up) for ``event``

    Allowed only for an authenticated member, only for an **upcoming** event
    (once the event date has passed no one may sign up — attendance can still be
    recorded by an officer afterwards), and only for events visible to the
    member's chapter (their own chapter's events or approved cross-chapter public
    events — reuses the WI-2 :meth:`~EventQuerySet.visible_to_chapter` logic).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if event.date < timezone.localdate():
        return False
    from thetatauCMT.events.models import Event

    chapter = user.current_chapter
    if chapter is None:
        return False
    return Event.objects.visible_to_chapter(chapter).filter(pk=event.pk).exists()


def rsvp_to_event(event, member):
    """Record ``member``'s RSVP as a ``signed_up`` AttendanceRecord (WI-10).

    Snapshot fields (active status, home chapter) come from
    :func:`record_attendance`. An existing ``attended`` record is never
    downgraded. Returns ``(record, created)``.
    """
    existing = AttendanceRecord.objects.filter(event=event, user=member).first()
    if existing and existing.status == AttendanceRecord.STATUS.ATTENDED:
        return existing, False
    return record_attendance(event, member, AttendanceRecord.STATUS.SIGNED_UP, member)


def cancel_rsvp(event, member):
    """Remove a member's own RSVP (WI-10). Deletes the ``signed_up`` record only.

    Attendance already marked ``attended`` / ``no_show`` by an officer is left
    untouched — a member can only cancel their own outstanding sign-up. Returns
    ``True`` if a sign-up was removed.
    """
    record = AttendanceRecord.objects.filter(event=event, user=member, status=AttendanceRecord.STATUS.SIGNED_UP).first()
    if record is None:
        return False
    record.delete()
    return True
