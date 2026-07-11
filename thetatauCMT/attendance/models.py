import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.events.models import Event


class AttendanceRecordQuerySet(models.QuerySet):
    def for_event(self, event):
        return self.filter(event=event)

    def attended(self):
        return self.filter(status=AttendanceRecord.STATUS.ATTENDED)

    def signed_up(self):
        return self.filter(status=AttendanceRecord.STATUS.SIGNED_UP)

    def no_show(self):
        return self.filter(status=AttendanceRecord.STATUS.NO_SHOW)

    def active_snapshot(self):
        return self.filter(was_active=True)


class AttendanceRecord(TimeStampedModel):
    """A single member's attendance for a single event.

    Snapshot fields (``was_active``, ``chapter``, ``recorded_by``,
    ``recorded_at``) capture the state at the moment attendance was recorded so
    the record stays historically accurate even if the member's status changes
    later. Lifecycle state is tracked in ``status`` (signed_up → attended /
    no_show); every change is appended to :class:`AttendanceStatusTransition`
    so the sign-up history is preserved (never overwritten).
    """

    class STATUS(models.TextChoices):
        SIGNED_UP = "signed_up", "Signed Up"
        ATTENDED = "attended", "Attended"
        NO_SHOW = "no_show", "No Show"

    objects = AttendanceRecordQuerySet.as_manager()

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="attendance_records")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    status = models.CharField(max_length=20, choices=STATUS.choices, default=STATUS.ATTENDED)
    was_active = models.BooleanField(
        default=False,
        help_text="Member's active status at the time attendance was recorded.",
    )
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.PROTECT,
        related_name="attendance_records",
        help_text="Snapshot of the member's home chapter at record time (differs from the event chapter for guests).",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_recorded",
    )
    recorded_at = models.DateTimeField(default=timezone.now)
    # Denormalised quick-access for the most recent transition; the full,
    # append-only history lives in ``transitions`` (AttendanceStatusTransition).
    previous_status = models.CharField(max_length=20, blank=True, default="")
    transitioned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ("event", "user")
        ordering = ["-recorded_at"]

    def __str__(self):
        return f"{self.user} {self.get_status_display()} @ {self.event}"

    @property
    def is_guest(self):
        """True when the member's home chapter differs from the event's chapter."""
        return bool(self.event.chapter_id) and self.chapter_id != self.event.chapter_id

    def log_transition(self, from_status, to_status, changed_by=None):
        """Append a transition to the history log."""
        return AttendanceStatusTransition.objects.create(
            record=self,
            from_status=from_status or "",
            to_status=to_status,
            changed_by=changed_by,
        )

    def set_status(self, new_status, changed_by=None, commit=True):
        """Transition to ``new_status`` and record the change in history.

        Preserves the sign-up history: the record itself is not duplicated, but
        each status change is appended to :class:`AttendanceStatusTransition`.
        A no-op change (same status) does nothing.
        """
        old_status = self.status
        if old_status == new_status:
            return self
        self.previous_status = old_status
        self.status = new_status
        self.transitioned_at = timezone.now()
        if commit:
            self.save(update_fields=["previous_status", "status", "transitioned_at", "modified"])
        self.log_transition(old_status, new_status, changed_by=changed_by)
        return self


class AttendanceStatusTransition(TimeStampedModel):
    """Append-only log of a single status change on an AttendanceRecord.

    Recommended history mechanism for WI-4: rather than mutating/deleting the
    sign-up record, every status change is logged here so the full lifecycle
    (signed_up → attended / no_show) is auditable.
    """

    record = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="transitions")
    from_status = models.CharField(max_length=20, blank=True, default="")
    to_status = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_transitions",
    )
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["changed_at", "pk"]

    def __str__(self):
        return f"{self.record_id}: {self.from_status or '∅'} → {self.to_status}"


class MatchQueueItem(TimeStampedModel):
    """An uploaded national-event attendance row that could not be matched to a
    member with sufficient confidence (WI-7), awaiting manual admin resolution.

    Stores the raw, as-uploaded identity fields plus the ranked candidate
    matches (with scores) produced by :mod:`attendance.matching`. Resolving an
    item creates the :class:`AttendanceRecord`. Re-uploads are idempotent: a
    stable ``fingerprint`` of the raw identity keeps duplicate rows from
    creating duplicate queue items, and already-resolved fingerprints are
    skipped on subsequent uploads.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        RESOLVED = "resolved", "Resolved"
        SKIPPED = "skipped", "Skipped"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="match_queue_items")
    upload_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="Groups all rows that arrived in the same upload.",
    )
    fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Stable hash of the raw identity fields; keeps re-uploads idempotent.",
    )
    # Raw, as-uploaded values — no member id is required.
    raw_member_id = models.CharField(max_length=100, blank=True, default="")
    raw_badge_number = models.CharField(max_length=100, blank=True, default="")
    raw_email = models.CharField(max_length=255, blank=True, default="")
    raw_name = models.CharField(max_length=255, blank=True, default="")
    raw_first_name = models.CharField(max_length=255, blank=True, default="")
    raw_last_name = models.CharField(max_length=255, blank=True, default="")
    raw_chapter = models.CharField(max_length=255, blank=True, default="")
    raw_graduation_year = models.CharField(max_length=16, blank=True, default="")
    raw_row = models.JSONField(
        default=dict,
        blank=True,
        help_text="The full original upload row, preserved for audit.",
    )
    # Ranked candidate matches: [{"user_id", "name", "score", "reasons", ...}].
    candidates = models.JSONField(default=list, blank=True)
    best_score = models.FloatField(
        default=0.0,
        help_text="Confidence (0..1) of the top candidate (below the auto-accept threshold).",
    )
    target_status = models.CharField(
        max_length=20,
        choices=AttendanceRecord.STATUS.choices,
        default=AttendanceRecord.STATUS.ATTENDED,
        help_text="Attendance status to assign when this row is resolved.",
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    resolved_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_match_resolutions",
    )
    attendance_record = models.ForeignKey(
        AttendanceRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="match_queue_items",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_matches_resolved",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_uploads",
    )
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created"]
        indexes = [models.Index(fields=["event", "status"])]

    def __str__(self):
        return f"MatchQueueItem({self.display_label} @ event {self.event_id}, {self.status})"

    @property
    def display_label(self):
        return self.raw_name or self.raw_email or self.raw_member_id or self.raw_badge_number or "(no identity)"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    def resolve_to(self, user, resolved_by, status=None):
        """Confirm a manual/candidate match: create (or upsert) the
        AttendanceRecord and mark this item resolved.

        Idempotent — :func:`attendance.services.record_attendance` upserts on the
        unique ``(event, user)`` constraint, so resolving twice never
        double-creates attendance.
        """
        from .services import record_attendance

        status = status or self.target_status
        record, _ = record_attendance(self.event, user, status, resolved_by)
        self.resolved_user = user
        self.attendance_record = record
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.status = self.Status.RESOLVED
        self.save(
            update_fields=[
                "resolved_user",
                "attendance_record",
                "resolved_by",
                "resolved_at",
                "status",
                "modified",
            ]
        )
        return record

    def skip(self, resolved_by, note=""):
        """Dismiss the row without creating attendance (no plausible match)."""
        self.status = self.Status.SKIPPED
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        if note:
            self.note = note
        self.save(update_fields=["status", "resolved_by", "resolved_at", "note", "modified"])
