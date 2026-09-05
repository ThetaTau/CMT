from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import (
    CHAPTER_OFFICER_REQUIRED,
    COMMITTEE_CHAIR,
    COUNCIL,
    NATIONAL_OFFICER,
    EnumClass,
    TimeStampedModel,
)
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.users.models import UserRoleChange


class PositionType(EnumClass):
    """The 4 position buckets used across the Transition Reports feature.

    Deliberately NOT a 1:1 mirror of the ``core.models`` role sets: pledge/new
    member educator and risk management chair live in
    ``core.models.COMMITTEE_CHAIR`` but are classified here as
    ``chapter_officer`` (required, core prompt set) per the
    CHAPTER_OFFICER_REQUIRED decision (transitions-app.md B4/B5).
    ``core.models.ADVISOR_ROLES`` is excluded from v1 and never appears here.
    """

    chapter_officer = ("CHAPTER_OFFICER", "Chapter Officer")
    council = ("COUNCIL", "Council")
    national_officer = ("NATIONAL_OFFICER", "National Officer")
    committee_chair = ("COMMITTEE_CHAIR", "Committee Chair")


def _build_position_key_to_type():
    """Map every in-scope position_key to its PositionType.

    Order matters: CHAPTER_OFFICER_REQUIRED is applied first so pledge/new
    member educator and risk management chair resolve to ``chapter_officer``,
    not ``committee_chair``, even though they are also in
    core.models.COMMITTEE_CHAIR.
    """
    mapping = {}
    for key in CHAPTER_OFFICER_REQUIRED:
        mapping[key] = PositionType.chapter_officer
    for key in COUNCIL:
        mapping.setdefault(key, PositionType.council)
    for key in NATIONAL_OFFICER:
        mapping.setdefault(key, PositionType.national_officer)
    for key in COMMITTEE_CHAIR:
        mapping.setdefault(key, PositionType.committee_chair)
    return mapping


POSITION_KEY_TO_TYPE = _build_position_key_to_type()

POSITION_KEY_CHOICES = sorted(
    ((key, key.title()) for key in POSITION_KEY_TO_TYPE),
    key=lambda pair: pair[0],
)


def position_type_for_key(position_key):
    """The ``PositionType`` for ``position_key``, or ``None`` if out of scope."""
    return POSITION_KEY_TO_TYPE.get(position_key)


class PositionOverride(TimeStampedModel):
    """Per-position required/optional/excluded override (TRWI-1).

    Sparse table: a position with no row here uses its type-level default
    (chapter_officer positions are required; council/national_officer/
    committee_chair positions are optional, subject to the type-level
    enable/disable Config flags applied in services.py).
    """

    class Status(EnumClass):
        required = ("required", "Required")
        optional = ("optional", "Optional")
        excluded = ("excluded", "Excluded")

    position_key = models.CharField(max_length=50, choices=POSITION_KEY_CHOICES, unique=True)
    status = models.CharField(max_length=10, choices=[x.value for x in Status])

    class Meta:
        ordering = ["position_key"]
        verbose_name = "Position Override"

    def __str__(self):
        return f"{self.position_key} ({self.status})"


class FieldType(EnumClass):
    text = ("text", "Short text")
    long_text = ("long_text", "Long text")
    list = ("list", "List")
    date = ("date", "Date")
    contact = ("contact", "Contact")


# Controlled tag vocabulary (TRWI-11) -- keep short and stable so cross-chapter
# trend counts stay meaningful.
TAG_CHOICES = [
    ("success", "Success"),
    ("failure", "Failure"),
    ("contacts", "Contacts"),
    ("expertise", "Expertise"),
    ("calendar", "Calendar"),
    ("systems", "Systems"),
    ("continuity", "Continuity"),
    ("advice", "Advice"),
    ("risk", "Risk"),
]


class ReportTemplate(TimeStampedModel):
    """Per-position questionnaire template (TRWI-2).

    Resolution is 3-tier: exact (position_type, position_key) match -> the
    type-level default (blank position_key) -> the global default (blank
    position_type AND position_key). ``unique_together`` guarantees each tier
    has at most one row, so prompt edits happen in place via ``version``
    bumps rather than by creating parallel template rows.
    """

    position_type = models.CharField(max_length=20, choices=[x.value for x in PositionType], blank=True)
    position_key = models.CharField(max_length=50, choices=POSITION_KEY_CHOICES, blank=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = [("position_type", "position_key")]
        ordering = ["position_type", "position_key"]
        verbose_name = "Report Template"

    def __str__(self):
        return self.name


class TemplatePrompt(models.Model):
    """One question on a ``ReportTemplate`` (TRWI-2).

    ``prompt_key`` is a stable identity reused across templates/versions for
    the prior-answers view (TRWI-8) -- unique only within its own template,
    since the same key legitimately appears on multiple templates.
    """

    template = models.ForeignKey(ReportTemplate, on_delete=models.CASCADE, related_name="prompts")
    order = models.PositiveIntegerField(default=0)
    prompt_key = models.SlugField(max_length=50)
    label = models.CharField(max_length=255)
    help_text = models.TextField(blank=True)
    field_type = models.CharField(
        max_length=10,
        choices=[x.value for x in FieldType],
        default=FieldType.long_text.value[0],
    )
    is_required = models.BooleanField(default=True)
    min_chars = models.PositiveIntegerField(null=True, blank=True)
    max_chars = models.PositiveIntegerField(null=True, blank=True)
    tag = models.CharField(max_length=20, choices=TAG_CHOICES, blank=True)

    class Meta:
        unique_together = [("template", "prompt_key")]
        ordering = ["template", "order"]
        verbose_name = "Template Prompt"

    def __str__(self):
        return f"{self.prompt_key} ({self.template})"


class ReportObligation(models.Model):
    """One position-holder's transition report requirement (TRWI-3).

    Generated by the ``generate_transition_obligations`` management command
    from ``users.UserRoleChange`` rows -- every role change generates its own
    obligation from its own ``end`` (decision C7), never a single "chapter's
    nominal term end". ``role_change`` is a loose traceability link only
    (``SET_NULL``): ``term_start``/``term_end`` are copied at generation time
    and stay authoritative for this obligation from then on, so editing or
    deleting the source role change never cascades here.
    """

    class Status(EnumClass):
        open = ("open", "Open")
        submitted = ("submitted", "Submitted")
        na_vacant = ("na_vacant", "N/A - Vacant")
        missed = ("missed", "Missed")

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="report_obligations")
    position_type = models.CharField(max_length=20, choices=[x.value for x in PositionType])
    position_key = models.CharField(max_length=50, choices=POSITION_KEY_CHOICES)
    officer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transition_report_obligations",
    )
    role_change = models.ForeignKey(
        UserRoleChange,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_obligations",
    )
    term_start = models.DateField()
    term_end = models.DateField()
    due_date = models.DateField()
    is_required = models.BooleanField(default=True)
    status = models.CharField(
        max_length=10,
        choices=[x.value for x in Status],
        default=Status.open.value[0],
    )
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("chapter", "position_key", "term_start", "term_end")]
        ordering = ["-term_end"]
        verbose_name = "Report Obligation"

    def __str__(self):
        return f"{self.position_key} ({self.chapter}) due {self.due_date}"
