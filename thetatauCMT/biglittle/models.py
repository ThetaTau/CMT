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
