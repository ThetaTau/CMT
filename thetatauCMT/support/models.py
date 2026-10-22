from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class ChapterSupportAssignmentQuerySet(models.QuerySet):
    def current(self, on=None):
        """Assignments that cover ``on`` (default today): started, and not yet ended."""
        day = on or timezone.localdate()
        return self.filter(start__lte=day).filter(models.Q(end__isnull=True) | models.Q(end__gte=day))

    def ended(self, on=None):
        day = on or timezone.localdate()
        return self.filter(end__lt=day)

    def upcoming(self, on=None):
        day = on or timezone.localdate()
        return self.filter(start__gt=day)


class ChapterSupportAssignment(TimeStampedModel):
    """One chapter a Chapter Support Specialist (CSS) serves, for a span of dates.

    Access and emails come only from assignments that are current on the day, so ending
    an assignment (setting ``end``) removes access on the next request. Assignments are
    ended rather than deleted, which keeps the history of who covered which chapter.
    See docs/specs/chapter-support-specialist.md.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_assignments",
        verbose_name=_("Chapter Support Specialist"),
    )
    chapter = models.ForeignKey(
        "chapters.Chapter",
        on_delete=models.CASCADE,
        related_name="support_assignments",
    )
    start = models.DateField(_("Start date"), default=timezone.localdate)
    end = models.DateField(
        _("End date"),
        null=True,
        blank=True,
        help_text=_("Leave empty while the assignment is open. Access ends after this date."),
    )
    notes = models.TextField(blank=True, help_text=_("Only Chapter Support Specialist managers see this."))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Assigned by"),
    )
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = ChapterSupportAssignmentQuerySet.as_manager()

    class Meta:
        ordering = ["chapter__name", "-start"]
        verbose_name = "Chapter Support Specialist assignment"
        verbose_name_plural = "Chapter Support Specialist assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "chapter"],
                condition=models.Q(end__isnull=True),
                name="support_one_open_assignment_per_chapter",
            ),
            models.CheckConstraint(
                check=models.Q(end__isnull=True) | models.Q(end__gte=models.F("start")),
                name="support_assignment_end_not_before_start",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "end"], name="support_assignment_user_idx"),
            models.Index(fields=["chapter", "end"], name="support_assignment_chapter_idx"),
        ]

    def __str__(self):
        until = f" to {self.end:%Y-%m-%d}" if self.end else ""
        return f"{self.user} supports {self.chapter} from {self.start:%Y-%m-%d}{until}"

    def is_current(self, on=None):
        day = on or timezone.localdate()
        return self.start <= day and (self.end is None or self.end >= day)

    def clean(self):
        from .services import holds_css_role

        super().clean()
        errors = {}
        # The active-chapter and role checks apply when an assignment is made or moved, not
        # when it is only being ended: a chapter that has since closed, or a CSS whose role
        # has since ended, must still be able to have their assignment ended.
        original = None
        if not self._state.adding:
            original = (
                ChapterSupportAssignment.objects.filter(pk=self.pk).values("user_id", "chapter_id", "start").first()
            )
        chapter_changed = original is None or original["chapter_id"] != self.chapter_id
        person_or_start_changed = (
            original is None or original["user_id"] != self.user_id or original["start"] != self.start
        )
        if self.end and self.start and self.end < self.start:
            errors["end"] = _("The end date cannot be before the start date.")
        if self.chapter_id is not None and chapter_changed and not self.chapter.active:
            errors["chapter"] = _("Only active chapters can be assigned.")
        if self.user_id is not None:
            if self.chapter_id is not None and self.chapter_id == self.user.chapter_id:
                errors["chapter"] = _("This is the person's own chapter, so it cannot be assigned to them.")
            if self.start and person_or_start_changed and not holds_css_role(self.user, on=self.start):
                errors["user"] = _(
                    "This person does not hold the Chapter Support Specialist role on the start date. "
                    "Give them the role first."
                )
        if not errors and self.user_id is not None and self.chapter_id is not None and self.start:
            overlapping = ChapterSupportAssignment.objects.filter(user_id=self.user_id, chapter_id=self.chapter_id)
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if self.end:
                overlapping = overlapping.filter(start__lte=self.end)
            overlapping = overlapping.filter(models.Q(end__isnull=True) | models.Q(end__gte=self.start))
            if overlapping.exists():
                errors["start"] = _("These dates overlap another assignment of this person to this chapter.")
        if errors:
            raise ValidationError(errors)


class SupportDigestEntry(TimeStampedModel):
    """One chapter email a CSS gets through the daily and monthly digests (Q14, Q25).

    Time-sensitive emails also reach the CSS on CC as they are sent (``realtime``); the
    digest only lists those. Every other kind reaches the CSS only through the digest, so
    ``body_html`` keeps the rendered email for it.
    """

    class Kind(models.TextChoices):
        OFFICER_MONTHLY = "officer_monthly", _("Monthly chapter officer email")
        DUES = "dues", _("Dues roster and reminder")
        WORKFLOW_UPDATE = "workflow_update", _("Workflow update")
        WORKFLOW_ESCALATION = "workflow_escalation", _("Workflow escalation")
        AWARD = "award", _("Award granted")
        NME_REVISION = "nme_revision", _("NME program revision request")
        BYLAWS = "bylaws", _("Bylaws update")
        BALLOT = "ballot", _("Ballot opened or reminder")
        BALLOT_RECEIPT = "ballot_receipt", _("Ballot vote receipt")
        BALLOT_VOTE_REMOVED = "ballot_vote_removed", _("Ballot vote removed")
        EXPULSION = "expulsion", _("Expulsion notice")
        DISCIPLINARY = "disciplinary", _("Disciplinary Form 2 reminder or rejection")
        OFFICER_UPDATE = "officer_update", _("Officer update reminder")
        PNM_INITIATION = "pnm_initiation", _("PNM and initiation reminder")
        TRANSITION_PAST_DUE = "transition_past_due", _("Transition report past due")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_digest_entries",
        verbose_name=_("Chapter Support Specialist"),
    )
    chapter = models.ForeignKey(
        "chapters.Chapter",
        on_delete=models.CASCADE,
        related_name="support_digest_entries",
    )
    kind = models.CharField(max_length=30, choices=Kind.choices)
    subject = models.CharField(max_length=255)
    body_html = models.TextField(blank=True, help_text=_("The rendered email, kept only for digest-only emails."))
    link = models.URLField(max_length=500, blank=True)
    realtime = models.BooleanField(
        _("Already sent on CC"),
        default=False,
        help_text=_("True when the CSS was on CC of the email as it was sent."),
    )
    daily_sent_at = models.DateTimeField(null=True, blank=True)
    monthly_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created", "pk"]
        verbose_name = "CSS digest entry"
        verbose_name_plural = "CSS digest entries"
        indexes = [
            models.Index(fields=["user", "daily_sent_at"], name="support_digest_daily_idx"),
            models.Index(fields=["user", "created"], name="support_digest_created_idx"),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.user} ({self.chapter}): {self.subject}"
