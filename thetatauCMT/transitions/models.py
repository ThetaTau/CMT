from django.db import models

from core.models import (
    CHAPTER_OFFICER_REQUIRED,
    COMMITTEE_CHAIR,
    COUNCIL,
    NATIONAL_OFFICER,
    EnumClass,
    TimeStampedModel,
)


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
