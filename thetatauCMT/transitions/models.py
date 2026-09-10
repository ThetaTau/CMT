import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from upload_validator import FileTypeValidator

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


# Starting tag vocabulary (TRWI-11) -- still used for TemplatePrompt.tag's
# admin-curated choices (prompt authors pick from this fixed, small set so
# prompt-derived tags stay predictable). ReportTag.tag itself is no longer
# restricted to these: see TransitionTag, the free-form vocabulary "Additional
# tags" on the compose form draws from (2026-09 UI change).
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

    ``last_reminder_offset_sent`` (TRWI-4): the most recent -- i.e. most
    urgent/smallest -- configured reminder offset already acted on for this
    obligation, so the daily reminder command never re-sends the same
    threshold twice. Not reset on status change; simply stops advancing once
    reminders stop (status becomes ``submitted``/``na_vacant``).

    ``public_id`` (2026-09): the compose/close-vacant URLs key off this, not
    the bare auto-increment ``id`` -- a sequential integer in a URL lets a
    bad actor enumerate every obligation (e.g. incrementing ``/1/compose/``,
    ``/2/compose/``, ...) to probe for existence even though the view itself
    is access-controlled; a random UUID removes that avenue entirely.
    """

    class Status(EnumClass):
        open = ("open", "Open")
        submitted = ("submitted", "Submitted")
        na_vacant = ("na_vacant", "N/A - Vacant")
        missed = ("missed", "Missed")

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
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
    last_reminder_offset_sent = models.IntegerField(null=True, blank=True)
    generated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("chapter", "position_key", "term_start", "term_end")]
        ordering = ["-term_end"]
        verbose_name = "Report Obligation"

    def __str__(self):
        return f"{self.position_key} ({self.chapter}) due {self.due_date}"


class TransitionReport(TimeStampedModel):
    """The authored report for one obligation (TRWI-5).

    ``na_vacant`` closes an obligation WITHOUT a report (per spec) -- that
    path sets ``ReportObligation.status`` directly and never creates a
    ``TransitionReport`` row at all. ``na_vacant`` still appears in
    ``Status`` for schema completeness (matching the spec's field table) but
    in practice every actual row is ``draft`` or ``submitted``.

    Author may edit indefinitely, even long after their term ends (decision
    F15) -- there is no lock and no separate "editable" check anywhere here.
    ``modified`` (from TimeStampedModel) is the only "last touched" signal
    since ``submitted_at`` is set once, at first submission, and never moves.

    ``public_id`` (2026-09): the acknowledge URL keys off this, not the bare
    auto-increment ``id`` -- see ``ReportObligation.public_id``'s own note.
    """

    class Status(EnumClass):
        draft = ("draft", "Draft")
        submitted = ("submitted", "Submitted")
        na_vacant = ("na_vacant", "N/A - Vacant")

    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    obligation = models.OneToOneField(ReportObligation, on_delete=models.CASCADE, related_name="report")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="transition_reports")
    position_type = models.CharField(max_length=20, choices=[x.value for x in PositionType])
    position_key = models.CharField(max_length=50, choices=POSITION_KEY_CHOICES)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transition_reports_authored"
    )
    template = models.ForeignKey(ReportTemplate, on_delete=models.PROTECT, related_name="reports")
    template_version = models.PositiveIntegerField()
    status = models.CharField(
        max_length=10,
        choices=[x.value for x in Status],
        default=Status.draft.value[0],
    )
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Transition Report"

    def __str__(self):
        return f"{self.position_key} ({self.chapter}) -- {self.status}"

    @property
    def tag_list(self):
        """Comma-joined tag names on this report (TRWI-11 search results
        column). A plain property, not a queryset annotation -- avoids the
        filter/annotate "shared join" pitfall of combining an aggregate with
        ``search_reports``' own ``tags__tag=`` filter in the same query;
        call sites needing this on many rows should ``prefetch_related("tags")``
        first (``search_reports`` does). ``ReportTag.tag`` is free-form (no
        ``choices=``, 2026-09 UI change) -- this is the raw stored value,
        not a ``get_FOO_display()`` label (which no longer exists on it).
        """
        return ", ".join(tag.tag for tag in self.tags.all())


class ReportAnswer(models.Model):
    """One prompt's answer on a ``TransitionReport`` (TRWI-5).

    ``prompt_key``/``prompt_label_snapshot`` are denormalized so the
    prior-answers view (TRWI-8) and this answer's own display never break if
    the source ``TemplatePrompt`` is later edited or deleted -- ``prompt`` is
    a loose, nullable traceability link only, mirroring
    ``ReportObligation.role_change``'s exact reasoning.
    """

    report = models.ForeignKey(TransitionReport, on_delete=models.CASCADE, related_name="answers")
    prompt = models.ForeignKey(TemplatePrompt, on_delete=models.SET_NULL, null=True, blank=True, related_name="answers")
    prompt_key = models.SlugField(max_length=50)
    prompt_label_snapshot = models.CharField(max_length=255)
    value = models.TextField(blank=True)

    class Meta:
        unique_together = [("report", "prompt_key")]
        ordering = ["report", "prompt__order"]
        verbose_name = "Report Answer"

    def __str__(self):
        return f"{self.prompt_key} ({self.report})"


class ReportContact(models.Model):
    """A named contact captured on a ``TransitionReport`` (2026-09,
    structured-content pass, TRWI-13 proposal).

    Structured instead of buried in the ``campus_contacts``/``experts``
    prompts' free text -- makes contacts individually browsable and
    searchable (see ``TransitionsConfig.ready``'s watson ``fields=``) rather
    than only findable by hoping the right phrase survives a paraphrase in a
    full-text match. Contains real third-party PII (name/phone/email of
    someone who may not be a CMT member at all, e.g. a vendor or a campus
    contact) -- ``anonymizer/transitions.py`` registers this ``register_clean``,
    same category as ``ReportAnswer``/``ReportAttachment``, not ``register_skip``.
    """

    report = models.ForeignKey(TransitionReport, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=150)
    role_or_context = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["report", "name"]
        verbose_name = "Report Contact"

    def __str__(self):
        return self.name


class ReportKeyDate(models.Model):
    """A recurring date/deadline captured on a ``TransitionReport`` (2026-09,
    structured-content pass, TRWI-13 proposal).

    Structured instead of buried in the ``key_dates`` prompt's one-per-line
    free text, so the lead-time note stays attached to its own date instead
    of hoping it survives a full-text search. ``timing`` is deliberately a
    free-text ``CharField``, not a real ``DateField`` -- the real examples
    this was modeled on include recurring/relative timing ("usually in
    October or March", "before January") that a single calendar date cannot
    express, so this trades away strict chronological sorting for matching
    what officers actually write. No PII here (label/timing/lead-time text
    only) -- ``anonymizer/transitions.py`` registers this ``register_skip``.
    """

    report = models.ForeignKey(TransitionReport, on_delete=models.CASCADE, related_name="key_dates")
    label = models.CharField(max_length=200)
    timing = models.CharField(max_length=100, blank=True)
    lead_time_note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["report", "id"]
        verbose_name = "Report Key Date"

    def __str__(self):
        return self.label


def get_attachment_upload_path(instance, filename):
    """``transitions/<chapter-slug>/<report-pk>/<filename>`` -- mirrors ``notes.models.get_upload_path``."""
    return "/".join(["transitions", instance.report.chapter.slug, str(instance.report.pk), filename])


class ReportAttachment(models.Model):
    """An optional artifact uploaded alongside a ``TransitionReport`` (TRWI-5).

    ``category`` (2026-09, TRWI-13 proposal) is a soft hint, not an
    enforced requirement -- mirrors the formal "Executive Board Officer
    Transition Worksheet" template's own "Additional Information to Share"
    checklist (budgets, meeting minutes, vendor info, asset lists, ...), so
    attachments become filterable/groupable by kind instead of an
    undifferentiated pile of files.

    ``public_id`` (2026-09): the attachment-delete URL keys off this, not
    the bare auto-increment ``id`` -- see ``ReportObligation.public_id``'s
    own note.
    """

    class Category(EnumClass):
        budget = ("budget", "Budget / financial")
        minutes = ("minutes", "Meeting minutes")
        vendor_info = ("vendor_info", "Vendor / contact info")
        policy = ("policy", "Policy / bylaws / C&B")
        event_plan = ("event_plan", "Event plan / checklist")
        asset_list = ("asset_list", "Asset / inventory list")
        other = ("other", "Other")

    ALLOWED_FILE_TYPES = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ]

    report = models.ForeignKey(TransitionReport, on_delete=models.CASCADE, related_name="attachments")
    public_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    file = models.FileField(
        upload_to=get_attachment_upload_path,
        validators=[FileTypeValidator(allowed_types=ALLOWED_FILE_TYPES)],
    )
    description = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=20, choices=[x.value for x in Category], blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transition_report_attachments"
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["uploaded_at"]
        verbose_name = "Report Attachment"

    def __str__(self):
        return self.file.name


class ReportAcknowledgement(models.Model):
    """A successor's "I've read this" receipt for one ``TransitionReport``
    (TRWI-7) -- a read-receipt metric, arguably more valuable than submission
    rate.

    Dedicated model rather than reusing ``guides.UserAcknowledgement`` (which
    already models "user said got it to a thing" generically over a GFK) --
    avoids a new app depending on `guides`; spelling matches this codebase's
    ``UserAcknowledgement`` convention. Editing the report after
    acknowledgment does NOT reset or flag it (decision 2026-09-04) --
    acknowledgments persist regardless of later edits.
    """

    report = models.ForeignKey(TransitionReport, on_delete=models.CASCADE, related_name="acknowledgements")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="transition_report_acknowledgements"
    )
    acknowledged_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("report", "user")]
        ordering = ["-acknowledged_at"]
        verbose_name = "Report Acknowledgement"

    def __str__(self):
        return f"{self.user} acknowledged {self.report}"


class HandoffNotice(models.Model):
    """Dedupe record: the "handoff packet available" email has already been
    sent for a ``UserRoleChange`` taking office (TRWI-7), so the daily
    command never re-sends it. The packet view itself always reflects the
    CURRENT full history -- this only tracks the one-time notification, not
    the packet's content.
    """

    role_change = models.OneToOneField(
        UserRoleChange, on_delete=models.CASCADE, related_name="transition_handoff_notice"
    )
    sent_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Handoff notice sent for {self.role_change}"


class TransitionTag(models.Model):
    """Free-form tag vocabulary for ``ReportTag`` (2026-09 UI change).

    Backs the compose form's "Additional tags" autocomplete
    (``forms.ComposeReportForm.manual_tags``, ``TransitionTagAutocomplete``)
    -- any signed-in member may search existing tags or type a new one to
    create it inline, mirroring ``jobs.Keyword``'s own vocabulary pattern.
    The original ``TAG_CHOICES`` 9 values are seeded here by migration so
    prompt-derived tags (still drawn from ``TemplatePrompt.tag``'s fixed
    choices) always have a matching row.
    """

    name = models.CharField(max_length=50)

    class Meta:
        ordering = ["name"]
        verbose_name = "Transition Tag"

    def __str__(self):
        return self.name


class ReportTag(models.Model):
    """A tag on a ``TransitionReport`` (TRWI-11), for cross-chapter trend
    mining -- tag frequency, common themes.

    ``source="prompt"`` rows are derived automatically from
    ``TemplatePrompt.tag`` on submit (``services.derive_prompt_tags``) and
    are fully re-derived (deleted and recreated) every submission, so they
    always reflect the CURRENT template/answers. ``source="manual"`` rows
    are added/removed independently by the author
    (``services.set_manual_tags``) and are never touched by re-derivation.
    ``unique_together``: a tag is either present on a report or it isn't,
    regardless of how it got there.

    ``tag`` stores the ``TransitionTag.name`` value as plain text rather than
    an FK -- ``TransitionReport``'s own read/search/trend code all already
    works off this string (see ``services.py``), and keeping it a CharField
    means none of that had to change when ``TransitionTag`` was introduced.
    No longer restricted to ``TAG_CHOICES``: a manually-added tag can be any
    ``TransitionTag`` name, including one created on the fly.
    """

    class Source(EnumClass):
        prompt = ("prompt", "From prompt")
        manual = ("manual", "Manual")

    report = models.ForeignKey(TransitionReport, on_delete=models.CASCADE, related_name="tags")
    tag = models.CharField(max_length=50)
    source = models.CharField(max_length=10, choices=[x.value for x in Source])

    class Meta:
        unique_together = [("report", "tag")]
        ordering = ["report", "tag"]
        verbose_name = "Report Tag"

    def __str__(self):
        return f"{self.tag} ({self.report})"
