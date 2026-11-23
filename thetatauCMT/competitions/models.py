"""National Engineering Case Competition (docs/specs/case-competition.md).

Each academic year has one ``Competition`` with judged ``Round`` rows: the proposal, then the
final submission. Chapters take part through ``Participant`` rows and submit one ``Entry`` per
round, with an ``EntryFile`` for each of the round's ``SubmissionItem`` rows. The round's
``Judge`` rows score every entry on a ``Scorecard``, one ``CriterionScore`` per
``RubricCriterion``.

Every date and time belongs to the competition's own time zone (Eastern by default), whatever
the site's time zone is: the admin and the pages enter and show them in that zone.
"""

import os
import uuid
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field
from multiselectfield import MultiSelectField

from core.models import NAT_OFFICERS, TimeStampedModel

DEFAULT_TIME_ZONE = "America/New_York"
TIME_ZONE_CHOICES = [
    ("America/New_York", "Eastern"),
    ("America/Chicago", "Central"),
    ("America/Denver", "Mountain"),
    ("America/Phoenix", "Arizona"),
    ("America/Los_Angeles", "Pacific"),
]
DEFAULT_CONTACT_ROLE = "professional development director"
# Page addresses under /competitions/ that a competition's slug would hide.
RESERVED_SLUGS = frozenset({"current", "judging", "entry", "file", "member-autocomplete", "judge-autocomplete"})


def validate_days(value):
    """A list of whole days separated by commas, such as ``3, 1, 0``."""
    for part in value.split(","):
        if not part.strip().isdecimal():
            raise ValidationError(_("Use whole numbers of days separated by commas, such as 3, 1, 0."), code="invalid")


def parse_days(value):
    """``"3, 1, 0"`` as ``[3, 1, 0]``; blank is ``[]``."""
    return [int(part) for part in (value or "").split(",") if part.strip()]


def announcement_path(instance, filename):
    return "/".join(["competitions", instance.slug or "competition", "announcement", _clean_name(filename)])


def entry_file_path(instance, filename):
    """``competitions/<competition>/round-<n>/<chapter>/<random>/<file name>``.

    The random folder makes the address impossible to guess (Q11 B: files are stored like other
    uploads, so anyone who has the address can open it). The upload keeps its own name.
    """
    entry = instance.entry
    return "/".join(
        [
            "competitions",
            entry.round.competition.slug,
            f"round-{entry.round.number}",
            entry.chapter.slug or str(entry.chapter_id),
            uuid.uuid4().hex,
            _clean_name(filename),
        ]
    )


def _clean_name(filename):
    try:
        name = get_valid_filename(os.path.basename(filename or ""))
    except SuspiciousFileOperation:
        name = "file"
    base, extension = os.path.splitext(name)
    return f"{base[:100] or 'file'}{extension[:10].lower()}"


class CompetitionQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True)


class Competition(TimeStampedModel):
    """One year's competition: the case, the page content, and the intent window."""

    name = models.CharField(max_length=200, default="National Engineering Case Competition")
    short_name = models.CharField(
        max_length=20, default="NECC", help_text=_("Used where space is tight, such as NECC.")
    )
    year_label = models.CharField(_("Year"), max_length=20, help_text=_("The academic year, such as 2026-2027."))
    slug = models.SlugField(max_length=80, unique=True, help_text=_("Used in page addresses, such as necc-2026-2027."))
    case_title = models.CharField(_("Case"), max_length=200, help_text=_("The case topic for the year."))
    case_description = CKEditor5Field(_("About the case"), blank=True)
    about = CKEditor5Field(_("About the competition"), blank=True, help_text=_("Purpose, timeline and awards."))
    resources = CKEditor5Field(blank=True, help_text=_("Links and other help, such as the recorded overview."))
    announcement = models.FileField(
        upload_to=announcement_path,
        max_length=255,
        blank=True,
        help_text=_("Optional. Any signed-in member can download it from the competition page."),
    )
    contact_role = models.CharField(
        max_length=100,
        blank=True,
        default=DEFAULT_CONTACT_ROLE,
        help_text=_(
            "The National Officer role to contact with questions. The page shows whoever holds it, and "
            "replies to the competition's emails go to them. The CASE_COMPETITION_CONTACT setting overrides "
            "this; with nobody in the role and no contact email, replies go to Central Office."
        ),
    )
    contact_email = models.EmailField(
        blank=True, help_text=_("Optional. Use this address instead of the role holder's own email.")
    )
    time_zone = models.CharField(
        max_length=40,
        choices=TIME_ZONE_CHOICES,
        default=DEFAULT_TIME_ZONE,
        help_text=_("Every date and time of the competition is entered and shown in this time zone."),
    )
    intent_opens_at = models.DateTimeField(_("Intent form opens"), null=True, blank=True)
    intent_closes_at = models.DateTimeField(
        _("Intent form closes"),
        null=True,
        blank=True,
        help_text=_("After it closes, chapters already taking part can still update their contacts."),
    )
    is_published = models.BooleanField(
        _("Published"), default=False, help_text=_("Members see the competition only once it is published.")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    objects = CompetitionQuerySet.as_manager()

    class Meta:
        ordering = ["-year_label", "-pk"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(intent_opens_at__isnull=True)
                | models.Q(intent_closes_at__isnull=True)
                | models.Q(intent_closes_at__gt=models.F("intent_opens_at")),
                name="competitions_intent_closes_after_it_opens",
            ),
        ]

    def __str__(self):
        return f"{self.name} {self.year_label}"

    def clean(self):
        errors = {}
        role = (self.contact_role or "").strip().lower()
        if role and role not in NAT_OFFICERS:
            errors["contact_role"] = _("Use a National Officer role, such as professional development director.")
        self.contact_role = role
        if self.intent_opens_at and self.intent_closes_at and self.intent_closes_at <= self.intent_opens_at:
            errors["intent_closes_at"] = _("The intent form must close after it opens.")
        if self.slug in RESERVED_SLUGS:
            errors["slug"] = _("This address is used by another page. Choose another, such as necc-2026-2027.")
        if errors:
            raise ValidationError(errors)

    @property
    def zone(self):
        return ZoneInfo(self.time_zone or DEFAULT_TIME_ZONE)

    @property
    def zone_label(self):
        return dict(TIME_ZONE_CHOICES).get(self.time_zone, self.time_zone)

    def local(self, value):
        """``value`` in the competition's time zone."""
        return timezone.localtime(value, self.zone) if value else None

    def format_time(self, value):
        """Such as ``Fri, Dec 11, 2026, 11:59 pm Eastern``; ``None`` when there is no value."""
        if value is None:
            return "None"
        local = self.local(value)
        hour = local.hour % 12 or 12
        meridiem = "am" if local.hour < 12 else "pm"
        return f"{local:%a, %b} {local.day}, {local.year}, {hour}:{local:%M} {meridiem} {self.zone_label}"


class KeyDate(TimeStampedModel):
    """A date shown on the competition page, such as the live Q&A. It drives nothing."""

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="key_dates")
    date = models.DateField()
    label = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    link = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ["competition_id", "date", "pk"]

    def __str__(self):
        return f"{self.date:%b} {self.date.day}, {self.date.year}: {self.label}"


class Round(TimeStampedModel):
    """A judged stage with its own window, rubric, files to collect and judges."""

    class Selection(models.TextChoices):
        ADVANCE = "advance", _("Choose qualifiers who advance")
        PLACES = "places", _("Award places")

    class Eligibility(models.TextChoices):
        PARTICIPANTS = "participants", _("Chapters taking part")
        ADVANCED = "advanced", _("Qualifiers from the previous round")

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="rounds")
    number = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    name = models.CharField(max_length=100, help_text=_("Such as Proposal or Final submission."))
    selection = models.CharField(max_length=10, choices=Selection.choices, default=Selection.ADVANCE)
    eligibility = models.CharField(
        _("Who can submit"),
        max_length=15,
        choices=Eligibility.choices,
        default=Eligibility.PARTICIPANTS,
        help_text=_("Only these chapters can submit and get the window's reminders."),
    )
    instructions = CKEditor5Field(blank=True, help_text=_("Format, length and what to include."))
    opens_at = models.DateTimeField(_("Window opens"))
    closes_at = models.DateTimeField(_("Window closes"))
    grace_minutes = models.PositiveSmallIntegerField(
        default=10,
        help_text=_("Uploads under way at the close are still accepted for this many minutes. 0 turns it off."),
    )
    judging_closes_at = models.DateTimeField(
        _("Judging deadline"), null=True, blank=True, help_text=_("Judge reminders count down to it.")
    )
    score_min = models.PositiveSmallIntegerField(
        _("Lowest score"), default=1, help_text=_("The lowest score a judge can give a criterion.")
    )
    advance_per_region = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text=_("Most qualifiers from one region. Empty means no limit.")
    )
    advance_total = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text=_("Most qualifiers in all. Empty means no limit.")
    )
    min_average_to_advance = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_("Lowest average score that can qualify. Empty means none."),
    )
    places = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text=_("How many places are awarded, such as 2 for first and second.")
    )
    share_feedback = models.BooleanField(
        default=True, help_text=_("Chapters read the judges' feedback, unsigned, once results are published.")
    )
    share_scores = models.BooleanField(
        default=False, help_text=_("Chapters see their average score for each criterion.")
    )
    share_rank = models.BooleanField(default=False, help_text=_("Chapters see their rank in their region."))
    reminder_days_before_open = models.CharField(
        max_length=50,
        blank=True,
        default="7",
        validators=[validate_days],
        help_text=_("Days before the window opens to remind chapters, separated by commas. Empty means none."),
    )
    reminder_days_before_close = models.CharField(
        max_length=50,
        blank=True,
        default="3,1,0",
        validators=[validate_days],
        help_text=_(
            "Days before the window closes to remind chapters that have not submitted; 0 is the closing day. "
            "Empty means none."
        ),
    )
    judge_reminder_days = models.CharField(
        max_length=50,
        blank=True,
        default="7,3,1",
        validators=[validate_days],
        help_text=_("Days before the judging deadline to remind judges with scorecards to do. Empty means none."),
    )
    results_published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("Set when a manager publishes the results (or announces the winners). Clearing it hides them."),
    )
    results_published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    rubric_locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_(
            "Set when the first scorecard is saved, so every judge scores the same criteria. Clear it only if "
            "the rubric must change, and tell the judges."
        ),
    )

    class Meta:
        ordering = ["competition_id", "number"]
        constraints = [
            models.UniqueConstraint(fields=["competition", "number"], name="competitions_round_number_unique"),
            models.CheckConstraint(
                check=models.Q(closes_at__gt=models.F("opens_at")), name="competitions_round_closes_after_it_opens"
            ),
            models.CheckConstraint(
                check=models.Q(judging_closes_at__isnull=True) | models.Q(judging_closes_at__gt=models.F("closes_at")),
                name="competitions_round_judging_after_the_close",
            ),
        ]

    def __str__(self):
        return f"{self.competition.short_name} {self.competition.year_label}, round {self.number}: {self.name}"

    def clean(self):
        errors = {}
        if self.opens_at and self.closes_at and self.closes_at <= self.opens_at:
            errors["closes_at"] = _("The window must close after it opens.")
        if self.closes_at and self.judging_closes_at and self.judging_closes_at <= self.closes_at:
            errors["judging_closes_at"] = _("The judging deadline must come after the window closes.")
        if self.eligibility == self.Eligibility.ADVANCED and (self.number or 0) <= 1:
            errors["eligibility"] = _("The first round has no qualifiers from a previous round.")
        if self.selection == self.Selection.PLACES and not self.places:
            errors["places"] = _("Set how many places are awarded.")
        if errors:
            raise ValidationError(errors)

    @property
    def is_published(self):
        return self.results_published_at is not None


class RubricCriterion(TimeStampedModel):
    """One line of a round's rubric. Judges give each a whole number of points."""

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="criteria")
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    max_points = models.PositiveSmallIntegerField(_("Highest score"), default=5, validators=[MinValueValidator(1)])
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["round_id", "order", "pk"]
        verbose_name = "rubric criterion"
        verbose_name_plural = "rubric criteria"
        constraints = [
            models.UniqueConstraint(fields=["round", "name"], name="competitions_criterion_name_unique"),
            models.CheckConstraint(check=models.Q(max_points__gte=1), name="competitions_criterion_scores_above_zero"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        if self.round_id and self.max_points is not None and self.max_points < self.round.score_min:
            raise ValidationError({"max_points": _("The highest score must be at least the round's lowest score.")})


class SubmissionItem(TimeStampedModel):
    """One thing a round collects from each chapter: a file or a link."""

    class Kind(models.TextChoices):
        FILE = "file", _("File upload")
        LINK = "link", _("Link")

    class FileType(models.TextChoices):
        PDF = "pdf", _("PDF")
        POWERPOINT = "powerpoint", _("PowerPoint")
        WORD = "word", _("Word")
        SPREADSHEET = "spreadsheet", _("Excel or CSV")
        IMAGE = "image", _("Image (JPEG or PNG)")

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="items")
    label = models.CharField(max_length=100)
    description = models.TextField(blank=True, help_text=_("Shown under the upload box."))
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.FILE)
    file_types = MultiSelectField(
        choices=FileType.choices, max_length=100, blank=True, help_text=_("For a file upload: the types accepted.")
    )
    max_size_mb = models.PositiveSmallIntegerField(
        _("Largest file (MB)"), default=50, validators=[MinValueValidator(1)]
    )
    required = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["round_id", "order", "pk"]
        constraints = [
            models.UniqueConstraint(fields=["round", "label"], name="competitions_item_label_unique"),
        ]

    def __str__(self):
        return self.label

    def clean(self):
        if self.kind == self.Kind.FILE and not self.file_types:
            raise ValidationError({"file_types": _("Choose at least one type of file.")})


class ParticipantQuerySet(models.QuerySet):
    def active(self):
        return self.filter(withdrawn_at__isnull=True)


class Participant(TimeStampedModel):
    """A chapter taking part in a competition; ``created`` is when it registered."""

    class Source(models.TextChoices):
        INTENT = "intent", _("Intent form")
        # Shown on the status page and in its CSV, so it never names the tool national uses.
        ADMIN = "admin", _("Added by national")
        SUBMISSION = "submission", _("First submission")

    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="participants")
    chapter = models.ForeignKey("chapters.Chapter", on_delete=models.CASCADE, related_name="competition_participations")
    source = models.CharField(_("How it registered"), max_length=12, choices=Source.choices, default=Source.ADMIN)
    contacts = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="competition_contact_for",
        help_text=_("The main contacts in charge of the submission. They get the chapter's competition emails."),
    )
    team_size_estimate = models.PositiveSmallIntegerField(_("Estimated team size"), null=True, blank=True)
    note = models.TextField(blank=True, help_text=_("A note from the chapter to national."))
    declared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Registered by"),
    )
    withdrawn_at = models.DateTimeField(
        _("Withdrawn"), null=True, blank=True, help_text=_("A withdrawn chapter gets no reminders.")
    )
    withdrawn_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    objects = ParticipantQuerySet.as_manager()

    class Meta:
        ordering = ["competition_id", "chapter__name"]
        verbose_name = "chapter taking part"
        verbose_name_plural = "chapters taking part"
        constraints = [
            models.UniqueConstraint(
                fields=["competition", "chapter"], name="competitions_one_registration_per_chapter"
            ),
        ]

    def __str__(self):
        return f"{self.chapter} in {self.competition}"

    def clean(self):
        if self._state.adding and self.chapter_id and not self.chapter.active:
            raise ValidationError({"chapter": _("Only active chapters can take part.")})


class Entry(TimeStampedModel):
    """A chapter's submission for one round."""

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="entries")
    chapter = models.ForeignKey("chapters.Chapter", on_delete=models.CASCADE, related_name="competition_entries")
    title = models.CharField(_("Project title"), max_length=200, blank=True)
    summary = models.TextField(max_length=1000, blank=True)
    submitted_at = models.DateTimeField(
        _("First complete"), null=True, blank=True, help_text=_("When the entry first had everything it needs.")
    )
    last_saved_at = models.DateTimeField(null=True, blank=True)
    last_saved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    last_saved_on_behalf = models.BooleanField(
        default=False, help_text=_("The last save was a manager's, on the chapter's behalf.")
    )
    deadline_override = models.DateTimeField(
        _("Extended deadline"),
        null=True,
        blank=True,
        help_text=_("This chapter's own deadline for the round, when a manager has given it an extension."),
    )
    eligible = models.BooleanField(default=True)
    ineligible_reason = models.TextField(blank=True, help_text=_("Shown to the chapter."))
    advanced = models.BooleanField(_("Qualified"), null=True, blank=True)
    place = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    manager_note = models.TextField(blank=True, help_text=_("Only managers see this."))

    class Meta:
        ordering = ["round_id", "chapter__name"]
        verbose_name_plural = "entries"
        constraints = [
            models.UniqueConstraint(fields=["round", "chapter"], name="competitions_one_entry_per_chapter_per_round"),
            models.UniqueConstraint(
                fields=["round", "place"],
                condition=models.Q(place__isnull=False),
                name="competitions_one_entry_per_place",
            ),
            models.CheckConstraint(
                check=models.Q(place__isnull=True) | models.Q(place__gte=1), name="competitions_place_from_one"
            ),
        ]

    def __str__(self):
        return f"{self.chapter}, round {self.round.number}: {self.title or 'Untitled'}"


class EntryMember(TimeStampedModel):
    """A member on a chapter's team for an entry, with their role on the team."""

    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name="team")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="competition_teams")
    team_role = models.CharField(max_length=100, blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["entry_id", "order", "pk"]
        verbose_name = "team member"
        constraints = [
            models.UniqueConstraint(fields=["entry", "user"], name="competitions_one_team_row_per_member"),
        ]

    def __str__(self):
        return f"{self.user}: {self.team_role or 'None'}"


class EntryFile(TimeStampedModel):
    """An uploaded file or a link for one item of an entry; ``created`` is when it arrived.

    Replacing a file keeps the old row with ``replaced_at`` set, so each item has one current
    file and managers can still open the old ones.
    """

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name="files")
    # RESTRICT, not PROTECT: an item with uploads cannot be deleted on its own, but deleting a whole
    # round or competition (which deletes its entries too) still works.
    item = models.ForeignKey(SubmissionItem, on_delete=models.RESTRICT, related_name="files")
    file = models.FileField(upload_to=entry_file_path, max_length=255, blank=True)
    link = models.URLField(max_length=500, blank=True)
    original_name = models.CharField(max_length=255, blank=True)
    size = models.PositiveBigIntegerField(_("Size in bytes"), null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    replaced_at = models.DateTimeField(
        null=True, blank=True, help_text=_("Empty while this is the item's current file.")
    )

    class Meta:
        ordering = ["entry_id", "item__order", "-created"]
        constraints = [
            models.UniqueConstraint(
                fields=["entry", "item"],
                condition=models.Q(replaced_at__isnull=True),
                name="competitions_one_current_file_per_item",
            ),
            models.CheckConstraint(check=~(models.Q(file="") & models.Q(link="")), name="competitions_file_or_link"),
        ]

    def __str__(self):
        return self.original_name or self.link or self.file.name


class JudgeQuerySet(models.QuerySet):
    def active(self):
        return self.filter(removed_at__isnull=True)


class Judge(TimeStampedModel):
    """Someone scoring a round. Removing a judge keeps their scorecards, which stop counting."""

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="judges")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="competition_judging")
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    removed_at = models.DateTimeField(null=True, blank=True)

    objects = JudgeQuerySet.as_manager()

    class Meta:
        ordering = ["round_id", "user__name"]
        constraints = [
            models.UniqueConstraint(fields=["round", "user"], name="competitions_one_judge_row_per_person"),
        ]

    def __str__(self):
        return f"{self.user} judging {self.round}"


class Assignment(TimeStampedModel):
    """One entry for one judge to score."""

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    judge = models.ForeignKey(Judge, on_delete=models.CASCADE, related_name="assignments")
    entry = models.ForeignKey(Entry, on_delete=models.CASCADE, related_name="assignments")
    stepped_aside_at = models.DateTimeField(
        null=True, blank=True, help_text=_("The judge stepped aside, such as for a conflict of interest.")
    )
    step_aside_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["judge_id", "entry__chapter__name"]
        constraints = [
            models.UniqueConstraint(fields=["judge", "entry"], name="competitions_one_assignment_per_judge_and_entry"),
        ]

    def __str__(self):
        return f"{self.judge.user} scoring {self.entry.chapter}"

    def clean(self):
        if not (self.judge_id and self.entry_id):
            return
        if self.judge.round_id != self.entry.round_id:
            raise ValidationError(_("The judge and the entry must belong to the same round."))
        if self.judge.user.chapter_id == self.entry.chapter_id:
            raise ValidationError(_("A judge never scores their own chapter's entry."))


class Scorecard(TimeStampedModel):
    """A judge's scores and feedback for one entry; a draft until ``submitted_at`` is set."""

    assignment = models.OneToOneField(Assignment, on_delete=models.CASCADE, related_name="scorecard")
    feedback = models.TextField(_("Feedback for the chapter"), blank=True)
    feedback_hidden = models.BooleanField(default=False, help_text=_("A manager hid this feedback from the chapter."))
    private_note = models.TextField(blank=True, help_text=_("Only managers see this."))
    submitted_at = models.DateTimeField(null=True, blank=True, help_text=_("Empty while it is a draft."))
    total = models.PositiveSmallIntegerField(null=True, blank=True)

    def __str__(self):
        return f"Scorecard: {self.assignment}"


class CriterionScore(TimeStampedModel):
    """A judge's points and comment for one criterion; points stay empty in a partial draft."""

    scorecard = models.ForeignKey(Scorecard, on_delete=models.CASCADE, related_name="scores")
    # RESTRICT, as for EntryFile.item: a scored criterion stays, unless its whole round goes.
    criterion = models.ForeignKey(RubricCriterion, on_delete=models.RESTRICT, related_name="scores")
    points = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    comment_hidden = models.BooleanField(default=False, help_text=_("A manager hid this comment from the chapter."))

    class Meta:
        ordering = ["scorecard_id", "criterion__order", "criterion_id"]
        constraints = [
            models.UniqueConstraint(fields=["scorecard", "criterion"], name="competitions_one_score_per_criterion"),
        ]

    def __str__(self):
        return f"{self.criterion}: {self.points if self.points is not None else 'None'}"

    def clean(self):
        if self.points is None or not self.criterion_id:
            return
        lowest = self.criterion.round.score_min
        if not lowest <= self.points <= self.criterion.max_points:
            raise ValidationError(
                {"points": _("Give between %(low)s and %(high)s.") % {"low": lowest, "high": self.criterion.max_points}}
            )


class NotificationLog(models.Model):
    """One competition email sent. ``key`` names what was sent, to whom and for which date.

    A send that finds its key already here is skipped, so the daily command never sends the
    same email twice. Keys of reminders include the date counted from, so moving a window's
    date starts its reminders over from the step due on the new date.
    """

    class Kind(models.TextChoices):
        WELCOME = "welcome", _("Registered")
        OPENS_SOON = "opens_soon", _("Window opens soon")
        OPEN = "open", _("Window is open")
        CLOSES_SOON = "closes_soon", _("Window closes soon")
        CLOSED_SUMMARY = "closed_summary", _("Window closed: summary for managers")
        JUDGING_OPEN = "judging_open", _("Judging is open")
        JUDGING_DUE = "judging_due", _("Scorecards due")
        RESULTS = "results", _("Results")
        WINNERS = "winners", _("Winners")

    key = models.CharField(max_length=255, unique=True)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    competition = models.ForeignKey(Competition, on_delete=models.CASCADE, related_name="notification_log")
    round = models.ForeignKey(Round, on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    chapter = models.ForeignKey("chapters.Chapter", on_delete=models.CASCADE, null=True, blank=True, related_name="+")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="+"
    )
    recipients = models.TextField(blank=True)
    sent_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-sent_at", "-pk"]
        verbose_name = "competition email sent"
        verbose_name_plural = "competition emails sent"

    def __str__(self):
        return f"{self.get_kind_display()} ({self.sent_at:%Y-%m-%d})"
