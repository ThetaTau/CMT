import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from multiselectfield import MultiSelectField
from viewflow.models import Process

from core.models import NAT_OFFICERS_CHOICES, TimeStampedModel


def get_badge_image_path(instance, filename):
    return f"awards/badges/{filename}"


def default_effective_date():
    """Default effective date for a grant: today (grants may be backdated)."""
    return timezone.now().date()


class AwardTypeQuerySet(models.QuerySet):
    def active(self):
        """Award types that are not retired (excluded from active lists)."""
        return self.filter(is_active=True)


class AwardTypeManager(models.Manager.from_queryset(AwardTypeQuerySet)):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class AwardType(TimeStampedModel):
    """Admin-managed catalog entry describing a kind of award.

    A single ``AwardType`` catalog is shared by every recipient kind (member /
    chapter / region / ...). Each entry configures how the award is granted
    (:attr:`grant_method`), who may nominate for it (:attr:`nominator_scope`),
    and the per-cycle winner rules that the award-cycle and grant machinery
    (built in later work items) enforce.
    """

    class Level(models.TextChoices):
        MEMBER = "member", _("Member")
        CHAPTER = "chapter", _("Chapter")
        REGION = "region", _("Region")
        ALUMNI = "alumni", _("Alumni")
        ACTIVE = "active", _("Active")
        PNM = "pnm", _("PNM")
        NATIONAL = "national", _("National")

    class GrantMethod(models.TextChoices):
        DIRECT = "direct", _("Direct grant")
        NOMINATION_WORKFLOW = "nomination_workflow", _("Nomination workflow")

    class Recurrence(models.TextChoices):
        ONE_TIME = "one_time", _("One-time")
        RECURRING = "recurring", _("Recurring")

    class NominatorScope(models.TextChoices):
        MEMBER = "member", _("Member")
        OFFICER = "officer", _("Officer")
        NATIONAL = "national", _("National")

    name = models.CharField(_("Name"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    eligibility = models.TextField(
        _("Eligibility"),
        blank=True,
        help_text="Who may receive this award, in plain language, shown on the award catalog "
        "and the nomination form. The configured eligibility rules are listed alongside it.",
    )
    category = models.CharField(
        _("Category"),
        max_length=255,
        blank=True,
        help_text="Optional grouping label for the award (admin-managed).",
    )
    level = models.CharField(
        _("Level"),
        max_length=20,
        choices=Level.choices,
        help_text="Determines the recipient kind and eligibility scope.",
    )
    badge_image = models.ImageField(
        _("Badge / icon"),
        upload_to=get_badge_image_path,
        blank=True,
        null=True,
        help_text="Badge or icon shown on profiles and inline next to names.",
    )
    points = models.IntegerField(
        _("Points"),
        null=True,
        blank=True,
        help_text="Optional weight for standings / rollups.",
    )
    grant_method = models.CharField(
        _("Grant method"),
        max_length=20,
        choices=GrantMethod.choices,
        default=GrantMethod.DIRECT,
        help_text="How the award is granted: directly or via a nomination workflow.",
    )
    recurrence = models.CharField(
        _("Recurrence"),
        max_length=20,
        choices=Recurrence.choices,
        default=Recurrence.ONE_TIME,
        help_text="Whether the award recurs each cycle or is granted only once.",
    )
    single_winner = models.BooleanField(
        _("Single winner per cycle"),
        default=False,
        help_text="Enforce exactly one winner per cycle when set.",
    )
    allow_multiple_winners = models.BooleanField(
        _("Allow multiple winners"),
        default=False,
        help_text="Allow more than one winner per cycle.",
    )
    allow_multiple_nominations = models.BooleanField(
        _("Allow multiple nominations"),
        default=False,
        help_text="Allow the same recipient to be nominated multiple times per cycle.",
    )
    nominator_scope = MultiSelectField(
        _("Nominator scope"),
        choices=NominatorScope.choices,
        max_length=50,
        blank=True,
        help_text="Which roles may nominate for this award; drives the per-role nomination lists.",
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text="Retired awards are excluded from active lists.",
    )
    auto_generate_certificate = models.BooleanField(
        _("Auto-generate certificate"),
        default=False,
        help_text="Automatically generate a certificate / letter when this award is granted.",
    )

    objects = AwardTypeManager()

    class Meta:
        ordering = ["name"]
        verbose_name = "Award Type"
        verbose_name_plural = "Award Types"

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)

    # --- Per-cycle winner / nomination rules -------------------------------
    # The rules live on the AwardType; an AwardCycle supplies the period context
    # they are enforced within. These are pure-logic helpers: callers pass the
    # per-cycle count (wired to real AwardGrant counts in AWI-3+).
    @property
    def winner_limit(self):
        """Maximum winners allowed per cycle; ``None`` means unlimited."""
        return 1 if self.single_winner else None

    def can_add_winner(self, current_winner_count):
        """Whether another winner may be granted in a cycle that already holds
        ``current_winner_count`` winners of this award.

        ``single_winner`` caps a cycle at one winner; otherwise multiple winners
        are allowed.
        """
        limit = self.winner_limit
        return limit is None or current_winner_count < limit

    def can_add_nomination(self, existing_nomination_count):
        """Whether another nomination for the same recipient is allowed in a
        cycle, given how many that recipient already has
        (``allow_multiple_nominations``).
        """
        return self.allow_multiple_nominations or existing_nomination_count < 1

    @property
    def recipient_kind(self):
        """The recipient kind this award's level targets: member / chapter / region.

        Member-ish levels (member / alumni / active / pnm / national) all grant to
        individual members; the chapter and region levels grant to those entities.
        """
        if self.level == self.Level.CHAPTER:
            return "chapter"
        if self.level == self.Level.REGION:
            return "region"
        return "member"


class AwardCycleQuerySet(models.QuerySet):
    def active_on(self, on_date):
        """Cycles whose period contains ``on_date`` (a null bound is open-ended)."""
        return self.filter(
            models.Q(start_date__isnull=True) | models.Q(start_date__lte=on_date),
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=on_date),
        )

    def current(self, on_date=None):
        """Active cycles on ``on_date`` (default today), most-recently-started first."""
        on_date = on_date or timezone.now().date()
        return self.active_on(on_date).order_by(models.F("start_date").desc(nulls_last=True), "-id")


class AwardCycle(TimeStampedModel):
    """A period within which awards are granted (year / term / event).

    Cycles are shared across award types -- they provide the *period context*
    that the per-award winner / nomination rules on :class:`AwardType` are
    enforced within. Recurring awards get one cycle per period; one-time awards
    may use a single cycle.
    """

    class PeriodType(models.TextChoices):
        YEAR = "year", _("Year")
        TERM = "term", _("Term")
        EVENT = "event", _("Event")

    name = models.CharField(
        _("Name"),
        max_length=255,
        help_text='Label for the award period, e.g. "2025", "Fall 2025", "2025 Convention".',
    )
    period_type = models.CharField(
        _("Period type"),
        max_length=10,
        choices=PeriodType.choices,
        default=PeriodType.YEAR,
    )
    start_date = models.DateField(_("Start date"), null=True, blank=True)
    end_date = models.DateField(
        _("End date"),
        null=True,
        blank=True,
        help_text="Leave blank for an open / ongoing award period.",
    )
    event = models.ForeignKey(
        "events.Event",
        on_delete=models.SET_NULL,
        related_name="award_cycles",
        null=True,
        blank=True,
        help_text="Optional link to an event, for event-based award periods.",
    )

    objects = AwardCycleQuerySet.as_manager()

    class Meta:
        ordering = ["-start_date", "name"]
        verbose_name = "Award Period"
        verbose_name_plural = "Award Periods"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": _("End date cannot be before the start date.")})

    def contains(self, on_date):
        """Whether ``on_date`` falls within this cycle (open-ended bounds included)."""
        if self.start_date and on_date < self.start_date:
            return False
        if self.end_date and on_date > self.end_date:
            return False
        return True

    @property
    def is_current(self):
        return self.contains(timezone.now().date())


class AwardGrantQuerySet(models.QuerySet):
    def active(self):
        """Grants that have not been revoked."""
        return self.filter(status=AwardGrant.Status.ACTIVE)

    def revoked(self):
        return self.filter(status=AwardGrant.Status.REVOKED)

    def for_cycle(self, award_type, cycle):
        return self.filter(award_type=award_type, cycle=cycle)


class AwardGrant(TimeStampedModel):
    """A single award granted to one recipient (member, chapter, or region).

    Recipients use three nullable foreign keys with a DB-level "exactly one
    recipient" constraint. This is recommended over a generic relation: the
    recipient set is small and fixed, and explicit FKs preserve referential
    integrity, admin raw-id pickers, and straightforward joins / filtering.

    Grants are never hard-deleted -- revoking sets :attr:`status` to ``revoked``
    and stamps who / when / why, preserving the full record and its audit trail.
    A backdated grant carries the historical :attr:`effective_date` (used for
    display and reporting) while :attr:`granted_at` stays the real system
    timestamp.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        REVOKED = "revoked", _("Revoked")

    class Source(models.TextChoices):
        DIRECT = "direct", _("Direct")
        NOMINATION = "nomination", _("Nomination")
        IMPORT = "import", _("Import")

    # Ordered (kind, field-name) pairs used by the recipient helpers below.
    RECIPIENT_FIELDS = (
        ("member", "recipient_member"),
        ("chapter", "recipient_chapter"),
        ("region", "recipient_region"),
    )

    award_type = models.ForeignKey(AwardType, on_delete=models.PROTECT, related_name="grants")
    cycle = models.ForeignKey(AwardCycle, on_delete=models.PROTECT, related_name="grants")

    # --- Polymorphic recipient (exactly one populated) ---------------------
    recipient_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="award_grants",
        null=True,
        blank=True,
    )
    recipient_chapter = models.ForeignKey(
        "chapters.Chapter",
        on_delete=models.PROTECT,
        related_name="award_grants",
        null=True,
        blank=True,
    )
    recipient_region = models.ForeignKey(
        "regions.Region",
        on_delete=models.PROTECT,
        related_name="award_grants",
        null=True,
        blank=True,
    )

    # --- Who / when / why --------------------------------------------------
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="award_grants_made",
    )
    granted_at = models.DateTimeField(
        _("Granted at"),
        default=timezone.now,
        help_text="Real system timestamp when the grant was recorded.",
    )
    effective_date = models.DateField(
        _("Effective date"),
        default=default_effective_date,
        help_text="Date the award takes effect; may be backdated for historical records.",
    )
    reason = models.TextField(_("Reason"), blank=True)
    status = models.CharField(
        _("Status"),
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    source = models.CharField(
        _("Source"),
        max_length=12,
        choices=Source.choices,
        default=Source.DIRECT,
    )

    # --- Revocation (never hard-delete) ------------------------------------
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="award_grants_revoked",
        null=True,
        blank=True,
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoke_reason = models.TextField(blank=True)

    objects = AwardGrantQuerySet.as_manager()

    class Meta:
        ordering = ["-effective_date", "-id"]
        verbose_name = "Award Grant"
        verbose_name_plural = "Award Grants"
        constraints = [
            models.CheckConstraint(
                check=(
                    (
                        models.Q(recipient_member__isnull=False)
                        & models.Q(recipient_chapter__isnull=True)
                        & models.Q(recipient_region__isnull=True)
                    )
                    | (
                        models.Q(recipient_member__isnull=True)
                        & models.Q(recipient_chapter__isnull=False)
                        & models.Q(recipient_region__isnull=True)
                    )
                    | (
                        models.Q(recipient_member__isnull=True)
                        & models.Q(recipient_chapter__isnull=True)
                        & models.Q(recipient_region__isnull=False)
                    )
                ),
                name="awards_grant_exactly_one_recipient",
            ),
        ]

    def __str__(self):
        return f"{self.award_type} \u2192 {self.recipient_display}"

    # --- Recipient helpers -------------------------------------------------
    @property
    def recipient(self):
        """The single populated recipient object (member / chapter / region)."""
        for _kind, field in self.RECIPIENT_FIELDS:
            if getattr(self, f"{field}_id") is not None:
                return getattr(self, field)
        return None

    @property
    def recipient_kind(self):
        for kind, field in self.RECIPIENT_FIELDS:
            if getattr(self, f"{field}_id") is not None:
                return kind
        return None

    @property
    def recipient_display(self):
        recipient = self.recipient
        return str(recipient) if recipient is not None else ""

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def is_revoked(self):
        return self.status == self.Status.REVOKED

    def _recipient_count(self):
        return sum(1 for _kind, field in self.RECIPIENT_FIELDS if getattr(self, f"{field}_id") is not None)

    def clean(self):
        super().clean()
        if self._recipient_count() != 1:
            raise ValidationError("Exactly one recipient (member, chapter, or region) must be set.")


class GrantAudit(models.Model):
    """Append-only audit trail for an :class:`AwardGrant`.

    One row per action (created / revoked / imported / updated). Never edited or
    deleted; :attr:`detail` holds an optional JSON snapshot or note.
    """

    class Action(models.TextChoices):
        CREATED = "created", _("Created")
        REVOKED = "revoked", _("Revoked")
        IMPORTED = "imported", _("Imported")
        UPDATED = "updated", _("Updated")

    grant = models.ForeignKey(AwardGrant, on_delete=models.CASCADE, related_name="audit_entries")
    action = models.CharField(max_length=12, choices=Action.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="award_grant_audits",
        null=True,
        blank=True,
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    detail = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["timestamp", "id"]
        verbose_name = "Grant Audit"
        verbose_name_plural = "Grant Audit Entries"

    def __str__(self):
        return f"{self.get_action_display()} (grant {self.grant_id})"


class EligibilityRuleManager(models.Manager):
    def get_by_natural_key(self, award_type_name, rule_type, member_status, hook_key):
        return self.get(
            award_type__name=award_type_name,
            rule_type=rule_type,
            member_status=member_status,
            hook_key=hook_key,
        )


class EligibilityRule(TimeStampedModel):
    """A single configurable eligibility rule attached to an :class:`AwardType`.

    Rules are additive filters combined by the eligibility engine
    (:mod:`thetatauCMT.awards.eligibility`): member-status filters, chapter /
    region scope restrictions, an explicit recipient-kind guard, or a pluggable
    custom hook (``hook_key`` + ``params``). New check types can be added without
    a migration by registering a hook.
    """

    class RuleType(models.TextChoices):
        MEMBER_STATUS = "member_status", _("Member status")
        CHAPTER_SCOPE = "chapter_scope", _("Chapter scope")
        REGION_SCOPE = "region_scope", _("Region scope")
        RECIPIENT_KIND = "recipient_kind", _("Recipient kind")
        CUSTOM_HOOK = "custom_hook", _("Custom hook")

    class MemberStatus(models.TextChoices):
        ACTIVE = "active", _("Active")
        ALUMNI = "alumni", _("Alumni")
        PNM = "pnm", _("PNM")

    award_type = models.ForeignKey(AwardType, on_delete=models.CASCADE, related_name="eligibility_rules")
    rule_type = models.CharField(_("Rule type"), max_length=20, choices=RuleType.choices)
    member_status = models.CharField(
        _("Member status"),
        max_length=10,
        choices=MemberStatus.choices,
        blank=True,
        help_text="For member-status rules: which member status is eligible.",
    )
    chapters = models.ManyToManyField(
        "chapters.Chapter",
        blank=True,
        related_name="award_eligibility_rules",
        help_text="For chapter-scope rules: the chapters recipients must belong to.",
    )
    regions = models.ManyToManyField(
        "regions.Region",
        blank=True,
        related_name="award_eligibility_rules",
        help_text="For region-scope rules: the regions recipients must belong to.",
    )
    hook_key = models.CharField(
        _("Hook key"),
        max_length=100,
        blank=True,
        help_text="For custom-hook rules: the registered key of the pluggable check.",
    )
    params = models.JSONField(
        _("Parameters"),
        default=dict,
        blank=True,
        help_text="Parameters for the custom hook (or the recipient-kind guard).",
    )

    objects = EligibilityRuleManager()

    class Meta:
        verbose_name = "Eligibility Rule"
        verbose_name_plural = "Eligibility Rules"

    def __str__(self):
        return f"{self.award_type} \u2014 {self.get_rule_type_display()}"

    def natural_key(self):
        return (self.award_type.name, self.rule_type, self.member_status, self.hook_key)

    natural_key.dependencies = ["awards.awardtype"]


def get_nomination_docs_path(instance, filename):
    return f"awards/nominations/{instance.pk}_{filename}"


class AwardNominationProcess(Process):
    """A nomination for an award, modelled as a viewflow ``Process``.

    Created by the role-scoped nomination entry (AWI-6). One nomination targets
    exactly one recipient (member / chapter / region), mirroring
    :class:`AwardGrant`. The approval workflow -- review -> approve (creates an
    ``AwardGrant``) / reject -- is wired up by the flow in AWI-7; the
    ``result`` / ``reject_reason`` / ``resulting_grant`` fields are populated
    there.
    """

    class Result(models.TextChoices):
        APPROVED = "approved", _("Approved")
        REJECTED = "rejected", _("Rejected")

    RECIPIENT_FIELDS = (
        ("member", "recipient_member"),
        ("chapter", "recipient_chapter"),
        ("region", "recipient_region"),
    )

    award_type = models.ForeignKey(AwardType, on_delete=models.PROTECT, related_name="nominations")
    cycle = models.ForeignKey(AwardCycle, on_delete=models.PROTECT, related_name="nominations")

    recipient_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="award_nominations",
        null=True,
        blank=True,
    )
    recipient_chapter = models.ForeignKey(
        "chapters.Chapter",
        on_delete=models.PROTECT,
        related_name="award_nominations",
        null=True,
        blank=True,
    )
    recipient_region = models.ForeignKey(
        "regions.Region",
        on_delete=models.PROTECT,
        related_name="award_nominations",
        null=True,
        blank=True,
    )

    nominator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="award_nominations_made",
    )
    justification = models.TextField(_("Justification"), blank=True)
    supporting_docs = models.FileField(
        _("Supporting documents"),
        upload_to=get_nomination_docs_path,
        null=True,
        blank=True,
    )

    # Populated by the AWI-7 approval workflow.
    result = models.CharField(_("Result"), max_length=10, choices=Result.choices, blank=True)
    reject_reason = models.TextField(_("Reject reason"), blank=True)
    resulting_grant = models.ForeignKey(
        "awards.AwardGrant",
        on_delete=models.SET_NULL,
        related_name="source_nomination",
        null=True,
        blank=True,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="award_nominations_reviewed",
        null=True,
        blank=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(_("Review notes"), blank=True)

    class Meta:
        verbose_name = "Award Nomination"
        verbose_name_plural = "Award Nominations"

    def __str__(self):
        return f"Nomination: {self.award_type} \u2192 {self.recipient_display}"

    # --- Recipient helpers (same polymorphic pattern as AwardGrant) --------
    @property
    def recipient(self):
        for _kind, field in self.RECIPIENT_FIELDS:
            if getattr(self, f"{field}_id") is not None:
                return getattr(self, field)
        return None

    @property
    def recipient_kind(self):
        for kind, field in self.RECIPIENT_FIELDS:
            if getattr(self, f"{field}_id") is not None:
                return kind
        return None

    @property
    def recipient_display(self):
        recipient = self.recipient
        return str(recipient) if recipient is not None else ""


def get_certificate_path(instance, filename):
    return f"awards/certificates/{instance.grant_id}_{filename}"


class GrantArtifact(models.Model):
    """A certificate / letter attached to an :class:`AwardGrant`.

    Either auto-generated from a template (``generated``) or manually uploaded
    (``uploaded``). Multiple artifacts per grant are allowed (e.g. a generated
    certificate plus an uploaded signed letter).
    """

    class ArtifactType(models.TextChoices):
        GENERATED = "generated", _("Generated")
        UPLOADED = "uploaded", _("Uploaded")

    grant = models.ForeignKey(AwardGrant, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=10, choices=ArtifactType.choices)
    file = models.FileField(_("Certificate / letter"), upload_to=get_certificate_path)
    generated_at = models.DateTimeField(null=True, blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="award_artifacts_created",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-id"]
        verbose_name = "Grant Artifact"
        verbose_name_plural = "Grant Artifacts"

    def __str__(self):
        return f"{self.get_artifact_type_display()} certificate for grant {self.grant_id}"

    @property
    def created_at(self):
        """The generation or upload time, whichever applies."""
        return self.generated_at or self.uploaded_at


class AwardDigestRun(models.Model):
    """A record of a monthly award-digest send, for idempotency.

    The digest command skips a period that already has a run (unless forced), so
    re-running it is safe and never double-sends.
    """

    period_start = models.DateField()
    period_end = models.DateField()
    sent_at = models.DateTimeField(default=timezone.now)
    grant_count = models.IntegerField(default=0)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="award_digests_sent",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-period_start"]
        verbose_name = "Award Digest Run"
        verbose_name_plural = "Award Digest Runs"
        constraints = [
            models.UniqueConstraint(fields=["period_start", "period_end"], name="awards_digest_unique_period"),
        ]

    def __str__(self):
        return f"Award digest {self.period_start} \u2013 {self.period_end} ({self.grant_count})"


def get_officer_badge_path(instance, filename):
    return f"awards/officer_badges/{filename}"


class OfficerBadge(TimeStampedModel):
    """A configurable icon for a national-officer role.

    Shown inline next to a member's name by the badge template tag (which also
    renders award badges), so officer status is visible site-wide.
    """

    role = models.CharField(_("Role"), max_length=100, choices=NAT_OFFICERS_CHOICES, unique=True)
    badge_image = models.ImageField(_("Badge image"), upload_to=get_officer_badge_path, blank=True, null=True)
    icon_class = models.CharField(
        _("Icon class"),
        max_length=100,
        blank=True,
        help_text="Optional CSS / FontAwesome class used when no image is set.",
    )
    short_label = models.CharField(
        _("Short label"),
        max_length=50,
        blank=True,
        help_text="Tooltip / alt text; defaults to the role name.",
    )
    is_active = models.BooleanField(_("Active"), default=True)

    class Meta:
        ordering = ["role"]
        verbose_name = "Officer Badge"
        verbose_name_plural = "Officer Badges"

    def __str__(self):
        return self.short_label or self.get_role_display()

    @property
    def display_label(self):
        return self.short_label or self.get_role_display()


class AwardImportMatchQueueItem(TimeStampedModel):
    """A legacy-import CSV row whose recipient could not be matched with enough
    confidence (AWI-13), awaiting manual admin resolution.

    Mirrors the attendance national-upload match queue: it stores the raw import
    row plus the ranked candidate recipients (with confidence scores) produced by
    :mod:`thetatauCMT.awards.import_matching`. The award type and cycle are
    resolved up front (rows whose award cannot be resolved are reported as import
    errors, not queued). Resolving an item creates the backdated ``import``
    :class:`AwardGrant`; a stable ``fingerprint`` of the raw identity keeps
    re-imports idempotent (no duplicate queue items, and already-resolved
    fingerprints are skipped).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        RESOLVED = "resolved", "Resolved"
        SKIPPED = "skipped", "Skipped"

    class RecipientKind(models.TextChoices):
        MEMBER = "member", "Member"
        CHAPTER = "chapter", "Chapter"
        REGION = "region", "Region"

    upload_id = models.UUIDField(
        default=uuid.uuid4,
        db_index=True,
        help_text="Groups all rows that arrived in the same import.",
    )
    fingerprint = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Stable hash of the raw identity fields; keeps re-imports idempotent.",
    )
    recipient_kind = models.CharField(max_length=10, choices=RecipientKind.choices)

    # Raw, as-uploaded values.
    raw_row = models.JSONField(default=dict, blank=True, help_text="The full original import row, preserved for audit.")
    raw_award = models.CharField(max_length=255, blank=True, default="")
    raw_recipient = models.CharField(max_length=255, blank=True, default="")
    raw_cycle = models.CharField(max_length=255, blank=True, default="")
    raw_effective_date = models.CharField(max_length=32, blank=True, default="")

    # Resolved award context (award types are admin-managed, so they must already
    # exist; cycles are created as needed during import).
    award_type = models.ForeignKey(
        AwardType,
        on_delete=models.SET_NULL,
        related_name="import_queue_items",
        null=True,
        blank=True,
    )
    cycle = models.ForeignKey(
        AwardCycle,
        on_delete=models.SET_NULL,
        related_name="import_queue_items",
        null=True,
        blank=True,
    )
    effective_date = models.DateField(null=True, blank=True)

    # Ranked candidate matches: [{"id", "name", "kind", "score", "reasons"}].
    candidate_matches = models.JSONField(default=list, blank=True)
    best_score = models.FloatField(default=0.0)
    import_error = models.TextField(blank=True, default="")

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)

    # Set on manual resolution (exactly one recipient FK, matching recipient_kind).
    resolved_recipient_member = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="award_import_resolutions",
        null=True,
        blank=True,
    )
    resolved_recipient_chapter = models.ForeignKey(
        "chapters.Chapter",
        on_delete=models.SET_NULL,
        related_name="award_import_resolutions",
        null=True,
        blank=True,
    )
    resolved_recipient_region = models.ForeignKey(
        "regions.Region",
        on_delete=models.SET_NULL,
        related_name="award_import_resolutions",
        null=True,
        blank=True,
    )
    resolved_grant = models.ForeignKey(
        AwardGrant,
        on_delete=models.SET_NULL,
        related_name="import_queue_items",
        null=True,
        blank=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="award_imports_resolved",
        null=True,
        blank=True,
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="award_imports_uploaded",
        null=True,
        blank=True,
    )
    note = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created"]
        verbose_name = "Award Import Match Queue Item"
        verbose_name_plural = "Award Import Match Queue Items"
        indexes = [models.Index(fields=["status", "fingerprint"])]

    def __str__(self):
        return f"AwardImportMatchQueueItem({self.display_label}, {self.status})"

    @property
    def display_label(self):
        return self.raw_recipient or "(no recipient)"

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    def _set_resolved_recipient(self, recipient):
        from thetatauCMT.chapters.models import Chapter
        from thetatauCMT.regions.models import Region
        from thetatauCMT.users.models import User

        self.resolved_recipient_member = recipient if isinstance(recipient, User) else None
        self.resolved_recipient_chapter = recipient if isinstance(recipient, Chapter) else None
        self.resolved_recipient_region = recipient if isinstance(recipient, Region) else None

    def resolve_to(self, recipient, resolved_by):
        """Confirm a recipient: create (or reuse) the backdated import grant and
        mark this item resolved. Idempotent -- reuses an existing grant for the
        same award / cycle / recipient rather than duplicating it."""
        from .importer import import_grant

        grant, _created = import_grant(
            self.award_type,
            self.cycle,
            recipient,
            resolved_by,
            effective_date=self.effective_date,
        )
        self._set_resolved_recipient(recipient)
        self.resolved_grant = grant
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.status = self.Status.RESOLVED
        self.save(
            update_fields=[
                "resolved_recipient_member",
                "resolved_recipient_chapter",
                "resolved_recipient_region",
                "resolved_grant",
                "resolved_by",
                "resolved_at",
                "status",
                "modified",
            ]
        )
        return grant

    def skip(self, resolved_by, note=""):
        """Dismiss the row without creating a grant (no plausible recipient)."""
        self.status = self.Status.SKIPPED
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        if note:
            self.note = note
        self.save(update_fields=["status", "resolved_by", "resolved_at", "note", "modified"])
