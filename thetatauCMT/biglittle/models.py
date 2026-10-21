from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel


class BigLittleQuerySet(models.QuerySet):
    def current(self):
        return self.filter(ended__isnull=True)

    def former(self):
        return self.filter(ended__isnull=False)


class BigLittle(TimeStampedModel):
    """One Big/Little pairing; ``ended`` is empty while it is the Little's current Big.

    Changing a Little's Big ends the old row instead of editing it, so former Bigs stay on
    record. There is deliberately no limit on Littles per Big ("twins").
    """

    class Source(models.TextChoices):
        INITIATION = "initiation", _("Initiation report")
        MEMBER = "member", _("Member")
        OFFICER = "officer", _("Officer")
        UPLOAD = "upload", _("CSV upload")
        ADMIN = "admin", _("Admin")

    big = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="links_as_big",
    )
    little = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="links_as_little",
    )
    # The Little's initiation chapter, so a later transfer does not move the pairing.
    chapter = models.ForeignKey(
        "chapters.Chapter",
        on_delete=models.CASCADE,
        related_name="big_little_links",
    )
    source = models.CharField(max_length=12, choices=Source.choices, default=Source.ADMIN)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Recorded by"),
    )
    ended = models.DateTimeField(null=True, blank=True)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    objects = BigLittleQuerySet.as_manager()

    class Meta:
        ordering = ["-created"]
        verbose_name = "Big/Little pairing"
        verbose_name_plural = "Big/Little pairings"
        constraints = [
            models.UniqueConstraint(
                fields=["little"],
                condition=models.Q(ended__isnull=True),
                name="biglittle_one_current_big_per_little",
            ),
            models.CheckConstraint(
                check=~models.Q(big=models.F("little")),
                name="biglittle_big_is_not_little",
            ),
        ]
        indexes = [models.Index(fields=["chapter", "ended"], name="biglittle_chapter_ended_idx")]

    def __str__(self):
        return f"{self.big} is the Big of {self.little}"

    @property
    def is_current(self):
        return self.ended is None


class PendingPairing(TimeStampedModel):
    """An uploaded row naming someone who did not match exactly one member of the chapter.

    It waits on the review page until a manager picks who the names mean, which saves the
    pairing, or dismisses it. ``fingerprint`` identifies the row's text, so uploading the
    same file again refreshes the waiting row instead of adding another one, and reuses the
    manager's answer once the row has been saved or dismissed.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Waiting for review")
        SAVED = "saved", _("Saved")
        DISMISSED = "dismissed", _("Dismissed")

    chapter = models.ForeignKey(
        "chapters.Chapter",
        on_delete=models.CASCADE,
        related_name="pending_big_little_rows",
    )
    fingerprint = models.CharField(max_length=64, help_text=_("Identifies the row's text across uploads."))
    line = models.PositiveIntegerField(default=0, help_text=_("Line number in the latest upload."))
    little_text = models.CharField(_("Little in the file"), max_length=255, blank=True)
    big_text = models.CharField(_("Big in the file"), max_length=255, blank=True)
    # A side that matched on upload, or the member picked on review.
    little = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    big = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    # [{"pk": member id, "score": 0..1}], best first.
    little_suggestions = models.JSONField(default=list, blank=True)
    big_suggestions = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Reviewed by"),
    )
    resolved_at = models.DateTimeField(_("Reviewed"), null=True, blank=True)

    class Meta:
        ordering = ["created", "line", "pk"]
        verbose_name = "Big/Little upload row to review"
        verbose_name_plural = "Big/Little upload rows to review"
        constraints = [
            models.UniqueConstraint(fields=["chapter", "fingerprint"], name="biglittle_pending_one_row_per_text"),
        ]
        indexes = [models.Index(fields=["chapter", "status"], name="biglittle_pending_status_idx")]

    def __str__(self):
        return f"Line {self.line}: {self.little_text or 'None'} / {self.big_text or 'None'}"
