import datetime
from dataclasses import dataclass

from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from watson import search as watson

from core.models import (
    CHAPTER_OFFICER_REQUIRED,
    NATIONAL_OFFICER,
    academic_encompass_start_end_date,
    semester_encompass_start_end_date,
)
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.configs.models import Config
from thetatauCMT.users.models import User, UserRoleChange

from .models import (
    POSITION_KEY_TO_TYPE,
    TAG_CHOICES,
    HandoffNotice,
    PositionOverride,
    PositionType,
    ReportAcknowledgement,
    ReportAnswer,
    ReportObligation,
    ReportTag,
    ReportTemplate,
    TransitionReport,
    position_type_for_key,
)
from .notifications import HandoffPacketAvailable, TransitionReportDueReminder, TransitionReportSeasonalReminder

DUE_DATE_OFFSET_DAYS_CONFIG_KEY = "TRANSITIONS_DUE_DATE_OFFSET_DAYS"
REMINDER_OFFSETS_DAYS_CONFIG_KEY = "TRANSITIONS_REMINDER_OFFSETS_DAYS"
SEASONAL_REMINDER_OFFSET_DAYS_CONFIG_KEY = "TRANSITIONS_SEASONAL_REMINDER_OFFSET_DAYS"
RD_ESCALATION_OFFSET_DAYS_CONFIG_KEY = "TRANSITIONS_RD_ESCALATION_OFFSET_DAYS"
# System-managed bookkeeping key (not an admin-tunable, despite living in the
# same Config table) -- see send_seasonal_reminder.
SEASONAL_REMINDER_LAST_SENT_FOR_CONFIG_KEY = "TRANSITIONS_SEASONAL_REMINDER_LAST_SENT_FOR"

DEFAULT_DUE_DATE_OFFSET_DAYS = 14
DEFAULT_REMINDER_OFFSETS_DAYS = (21, 14, 7, 1, -1, -7, -14)
DEFAULT_RD_ESCALATION_OFFSET_DAYS = -7

# TRWI-4: reminders continue through "missed" -- it is a visibility-only
# status (decision C7), not a stopping condition. Only submitted/na_vacant are
# "closure" per the acceptance criterion "reminders stop on submission/closure".
REMINDER_ELIGIBLE_STATUSES = (ReportObligation.Status.open.value[0], ReportObligation.Status.missed.value[0])

# TRWI-3: obligation generation window/tuning. Not Config-driven like the
# offsets above -- these govern the SCAN, not the business rule, and
# --lookahead-days is a CLI flag instead; see generate_transition_obligations.
# Per decision I22: catch up to a year of missed/late command runs.
LOOKBACK_GRACE_DAYS = 365
# Per decision I20: the vacancy safety net never reaches back further than
# this to pick a stale role change -- a position vacant for longer than that
# is better surfaced some other way than an obligation dated a year+ stale.
VACANCY_MAX_STALENESS_DAYS = 365
# Per decision I21: lookahead's job is to give every configured reminder
# offset (the largest being the most-days-before-due one) something to fire
# against, so it's derived from the offsets rather than a bare constant --
# see get_default_lookahead_days().
DEFAULT_LOOKAHEAD_BUFFER_DAYS = 10
DEFAULT_SEASONAL_REMINDER_OFFSET_DAYS = 30

# The Config flag gating each optional PositionType. chapter_officer has no
# entry -- it is always required, never gated by a flag (decision B4/B6).
TYPE_ENABLED_CONFIG_KEYS = {
    PositionType.council: "TRANSITIONS_COUNCIL_ENABLED",
    PositionType.national_officer: "TRANSITIONS_NATIONAL_OFFICER_ENABLED",
    PositionType.committee_chair: "TRANSITIONS_COMMITTEE_CHAIR_ENABLED",
}


def resolve_position_status(position_key):
    """The effective TRWI-1 status for ``position_key``.

    Returns ``"required"``, ``"optional"``, or ``"excluded"``, or ``None``
    if ``position_key`` is out of scope entirely (e.g. an ADVISOR_ROLES key).

    Resolution order: an explicit ``PositionOverride`` row always wins.
    Otherwise ``chapter_officer`` positions are required; the other three
    types are optional unless their type-level Config flag is off, in which
    case they resolve to "excluded".
    """
    position_type = position_type_for_key(position_key)
    if position_type is None:
        return None

    override = PositionOverride.objects.filter(position_key=position_key).first()
    if override is not None:
        return override.status

    if position_type == PositionType.chapter_officer:
        return PositionOverride.Status.required.name

    config_key = TYPE_ENABLED_CONFIG_KEYS[position_type]
    if not Config.feature_enabled(config_key):
        return PositionOverride.Status.excluded.name
    return PositionOverride.Status.optional.name


def is_position_required(position_key):
    """Whether ``position_key`` currently owes a Transition Report."""
    return resolve_position_status(position_key) == PositionOverride.Status.required.name


def resolve_template(position_key):
    """The active ``ReportTemplate`` for ``position_key`` (TRWI-2).

    Resolution order: exact ``position_key`` match -> the position_type's
    default template (blank position_key) -> the global default template
    (blank position_type and position_key). Returns ``None`` if
    ``position_key`` is out of scope, or nothing resolves at any tier.
    """
    position_type = position_type_for_key(position_key)
    if position_type is None:
        return None
    type_value = position_type.value[0]

    exact = ReportTemplate.objects.filter(is_active=True, position_type=type_value, position_key=position_key).first()
    if exact is not None:
        return exact

    type_default = ReportTemplate.objects.filter(is_active=True, position_type=type_value, position_key="").first()
    if type_default is not None:
        return type_default

    return ReportTemplate.objects.filter(is_active=True, position_type="", position_key="").first()


def _parse_config_int(config_key, default):
    raw = Config.get_value(config_key).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def get_due_date_offset_days():
    return _parse_config_int(DUE_DATE_OFFSET_DAYS_CONFIG_KEY, DEFAULT_DUE_DATE_OFFSET_DAYS)


def get_seasonal_reminder_offset_days():
    return _parse_config_int(SEASONAL_REMINDER_OFFSET_DAYS_CONFIG_KEY, DEFAULT_SEASONAL_REMINDER_OFFSET_DAYS)


def get_reminder_offsets_days():
    """Parsed, ordered list of reminder offsets (positive=before due, negative=after)."""
    raw = Config.get_value(REMINDER_OFFSETS_DAYS_CONFIG_KEY).strip()
    if not raw:
        return list(DEFAULT_REMINDER_OFFSETS_DAYS)
    offsets = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            offsets.append(int(chunk))
        except ValueError:
            continue
    return offsets or list(DEFAULT_REMINDER_OFFSETS_DAYS)


def get_default_lookahead_days():
    """Default forward scan window for ``generate_obligations`` (decision I21).

    ``due_date_offset + largest configured reminder offset + a fixed buffer``,
    so an obligation is always generated with enough runway for every
    configured reminder offset to have something to fire against -- raising
    the reminder offsets (TRWI-1 Config) widens this automatically instead of
    needing a matching manual bump here.
    """
    return get_due_date_offset_days() + max(get_reminder_offsets_days()) + DEFAULT_LOOKAHEAD_BUFFER_DAYS


def _upsert_obligation(*, chapter, position_key, role_change, officer, term_start, term_end, is_required):
    """Create the obligation if it doesn't exist yet; never touch an existing one.

    ``get_or_create``'s ``defaults`` only apply on creation, so a previously
    generated obligation's derived fields (officer/due_date/status/...) are
    never rewritten on a later run -- they become authoritative once
    generated, per the ReportObligation docstring / decision E12.
    """
    return ReportObligation.objects.get_or_create(
        chapter=chapter,
        position_key=position_key,
        term_start=term_start,
        term_end=term_end,
        defaults={
            "position_type": position_type_for_key(position_key).value[0],
            "officer": officer,
            "role_change": role_change,
            "due_date": term_end - datetime.timedelta(days=get_due_date_offset_days()),
            "is_required": is_required,
        },
    )


def generate_obligations(lookahead_days=None, dry_run=False):
    """Generate/refresh ``ReportObligation`` rows from ``UserRoleChange`` (TRWI-3).

    Two independent triggers, both keyed on the same natural key so re-running
    never duplicates:

    1. **Term ending soon** -- every in-scope role change whose ``end`` falls
       in ``[today - LOOKBACK_GRACE_DAYS, today + lookahead_days]`` gets an
       obligation with ``officer=role_change.user`` (the outgoing officer
       writes the report). ``lookahead_days`` defaults to
       ``get_default_lookahead_days()`` when not given. Positions resolving
       to "excluded" (per-position override or a disabled optional-type
       Config flag) are skipped entirely -- no obligation is generated for
       them.
    2. **Already-vacant safety net** -- for ``CHAPTER_OFFICER_REQUIRED``
       positions only (mirrors ``Chapter.get_about_expired_coucil()``'s exact
       scope): a chapter with no current-or-future holder for a required
       position gets an obligation from its most recent past role change
       with ``officer=None`` so the Regent can close it ``na_vacant`` --
       PROVIDED that role change ended within ``VACANCY_MAX_STALENESS_DAYS``
       (decision I20: never build a vacancy obligation off a holder from more
       than a year ago). A position never held at all, or last held longer
       ago than that, is skipped -- there is nothing to generate from.

    Finally, in the same run, every past-due ``open`` obligation is marked
    ``missed`` (visibility only, per decision C7 -- an unreachable outgoing
    officer is an accepted missed outcome, not a blocker).

    Wrapped in one transaction so ``dry_run`` writes nothing; returns counts.
    """
    if lookahead_days is None:
        lookahead_days = get_default_lookahead_days()
    today = timezone.now().date()
    window_start = today - datetime.timedelta(days=LOOKBACK_GRACE_DAYS)
    window_end = today + datetime.timedelta(days=lookahead_days)
    counts = {"term_end_created": 0, "vacant_created": 0, "missed": 0}

    with transaction.atomic():
        role_changes = UserRoleChange.objects.filter(
            role__in=list(POSITION_KEY_TO_TYPE),
            end__gte=window_start,
            end__lte=window_end,
        ).select_related("user")
        for role_change in role_changes:
            status = resolve_position_status(role_change.role)
            if status not in (PositionOverride.Status.required.name, PositionOverride.Status.optional.name):
                continue
            _, created = _upsert_obligation(
                chapter=role_change.user.chapter,
                position_key=role_change.role,
                role_change=role_change,
                officer=role_change.user,
                term_start=role_change.start,
                term_end=role_change.end,
                is_required=status == PositionOverride.Status.required.name,
            )
            if created:
                counts["term_end_created"] += 1

        for chapter in Chapter.objects.exclude(active=False):
            for role in CHAPTER_OFFICER_REQUIRED:
                status = resolve_position_status(role)
                if status not in (PositionOverride.Status.required.name, PositionOverride.Status.optional.name):
                    continue
                vacant_now = not UserRoleChange.objects.filter(
                    user__chapter=chapter, role=role, end__gte=today
                ).exists()
                if not vacant_now:
                    continue
                stale = (
                    UserRoleChange.objects.filter(
                        user__chapter=chapter,
                        role=role,
                        end__gte=today - datetime.timedelta(days=VACANCY_MAX_STALENESS_DAYS),
                    )
                    .order_by("-end")
                    .first()
                )
                if stale is None:
                    continue
                _, created = _upsert_obligation(
                    chapter=chapter,
                    position_key=role,
                    role_change=stale,
                    officer=None,
                    term_start=stale.start,
                    term_end=stale.end,
                    is_required=status == PositionOverride.Status.required.name,
                )
                if created:
                    counts["vacant_created"] += 1

        counts["missed"] = ReportObligation.objects.filter(
            status=ReportObligation.Status.open.value[0],
            due_date__lt=today,
        ).update(status=ReportObligation.Status.missed.value[0])

        if dry_run:
            transaction.set_rollback(True)

    return counts


def get_rd_escalation_offset_days():
    return _parse_config_int(RD_ESCALATION_OFFSET_DAYS_CONFIG_KEY, DEFAULT_RD_ESCALATION_OFFSET_DAYS)


def _current_reminder_threshold(days_until_due, offsets):
    """The most urgent configured offset already crossed, or ``None`` if none yet.

    "Crossed" means ``days_until_due <= offset``. The most urgent (smallest,
    i.e. most past-due) crossed offset wins, so a daily command that missed a
    few days jumps straight to where it should be rather than replaying every
    skipped step.
    """
    crossed = [offset for offset in offsets if days_until_due <= offset]
    return min(crossed) if crossed else None


def _regent_emails(chapter):
    email = chapter.generic_email_for_role("regent")
    return {email} if email else set()


def _rd_emails(chapter):
    region = chapter.region
    emails = set()
    for director in region.directors.all():
        emails |= {email for email in director.emails if email}
    if region.email:
        emails.add(region.email)
    return emails


def send_due_date_reminders(dry_run=False):
    """Per-officer reminders at configured offsets (TRWI-4 mechanism 1).

    For every obligation still owed (``REMINDER_ELIGIBLE_STATUSES`` -- missed
    is visibility-only, not a stopping condition), finds the most urgent
    configured offset already crossed and, if it is newer than
    ``last_reminder_offset_sent``, sends one reminder. Recipients escalate
    with urgency: the officer (if any) always; the chapter's Regent once past
    due; the region's RD once at/past ``get_rd_escalation_offset_days()``. If
    nobody resolves (e.g. a vacant obligation not yet past due), nothing is
    sent, but the threshold is still recorded so it is never re-evaluated.

    ``dry_run`` skips every send/write explicitly (this has a real external
    side effect -- an actual email send -- so unlike ``generate_obligations``
    this is NOT implemented via a rolled-back transaction). Returns the count
    of reminders sent (or that would be sent, under ``dry_run``).
    """
    today = timezone.now().date()
    offsets = get_reminder_offsets_days()
    rd_escalation_offset = get_rd_escalation_offset_days()
    sent = 0

    obligations = ReportObligation.objects.filter(status__in=REMINDER_ELIGIBLE_STATUSES).select_related(
        "officer", "chapter", "chapter__region"
    )
    for obligation in obligations:
        days_until_due = (obligation.due_date - today).days
        threshold = _current_reminder_threshold(days_until_due, offsets)
        if threshold is None:
            continue
        if obligation.last_reminder_offset_sent is not None and threshold >= obligation.last_reminder_offset_sent:
            continue

        emails = set(obligation.officer.emails) if obligation.officer else set()
        past_due = threshold < 0
        escalate_to_rd = threshold <= rd_escalation_offset
        if past_due:
            emails |= _regent_emails(obligation.chapter)
        if escalate_to_rd:
            emails |= _rd_emails(obligation.chapter)

        if emails:
            if not dry_run:
                TransitionReportDueReminder(obligation, emails, past_due, escalate_to_rd).send()
            sent += 1
        if not dry_run:
            obligation.last_reminder_offset_sent = threshold
            obligation.save(update_fields=["last_reminder_offset_sent"])

    return sent


def send_seasonal_reminder(dry_run=False):
    """Once-per-semester broadcast nudge (TRWI-4 mechanism 2).

    Fires when today is within ``get_seasonal_reminder_offset_days()`` of the
    CURRENT semester's end (``core.models.semester_encompass_start_end_date``)
    and hasn't already fired for that exact end date -- tracked via the
    ``TRANSITIONS_SEASONAL_REMINDER_LAST_SENT_FOR`` Config value. A NEW Config
    row is created to record it (not an update) since ``Config.get_value``
    already reads the latest row by ``created``, matching how every other
    Config value in this codebase is written. One individual email per user
    who currently owns at least one ``open`` obligation, listing all of them.

    ``dry_run`` skips every send/write explicitly, same reasoning as
    ``send_due_date_reminders``. Returns the count of users emailed (or who
    would be emailed under ``dry_run``); 0 if the window/dedupe gate didn't
    fire at all.
    """
    today = timezone.now().date()
    _, semester_end = semester_encompass_start_end_date()
    semester_end = semester_end.date()
    if not (0 <= (semester_end - today).days <= get_seasonal_reminder_offset_days()):
        return 0
    if Config.get_value(SEASONAL_REMINDER_LAST_SENT_FOR_CONFIG_KEY) == semester_end.isoformat():
        return 0

    officers = User.objects.filter(
        transition_report_obligations__status=ReportObligation.Status.open.value[0]
    ).distinct()
    sent = 0
    for officer in officers:
        obligations = officer.transition_report_obligations.filter(
            status=ReportObligation.Status.open.value[0]
        ).select_related("chapter")
        if not dry_run:
            TransitionReportSeasonalReminder(officer, obligations).send()
        sent += 1

    if not dry_run:
        Config.objects.create(
            key=SEASONAL_REMINDER_LAST_SENT_FOR_CONFIG_KEY,
            value=semester_end.isoformat(),
            description=(
                "TRWI-4 bookkeeping (system-managed, not admin-tunable): semester-end "
                "date the seasonal transition-report reminder was last sent for."
            ),
        )

    return sent


def send_transition_report_reminders(dry_run=False):
    """Both TRWI-4 reminder mechanisms -- what the daily command runs."""
    return {
        "due_date_reminders_sent": send_due_date_reminders(dry_run=dry_run),
        "seasonal_reminders_sent": send_seasonal_reminder(dry_run=dry_run),
    }


def get_my_open_obligations(user):
    """The viewer's own open/missed obligations, for the home dashboard card (TRWI-4)."""
    return (
        ReportObligation.objects.filter(officer=user, status__in=REMINDER_ELIGIBLE_STATUSES)
        .select_related("chapter")
        .order_by("due_date")
    )


# ---------------------------------------------------------------------------
# TRWI-5: compose & submit
# ---------------------------------------------------------------------------
REGENT_ROLE_KEY = "regent"


def get_my_obligations(user):
    """Every one of the viewer's own obligations, any status (TRWI-5 Transitions
    list). Broader than ``get_my_open_obligations`` (TRWI-4's home card, which
    is open/missed only) -- this one doubles as the viewer's own submission
    history, so submitted/na_vacant rows belong here too.
    """
    return ReportObligation.objects.filter(officer=user).select_related("chapter").order_by("-term_end")


def get_no_obligations_reason(user):
    """Why ``user`` has no ``ReportObligation`` row at all (any status) --
    for the "My Reports" empty state, so a member isn't left wondering
    whether that's a bug. Only meaningful when ``get_my_obligations(user)``
    is empty; ``generate_obligations`` only ever creates a row once a
    tracked role's term end falls within its lookahead window (TRWI-3), so
    an empty result always comes down to one of:

    1. No CURRENT role in an in-scope position (``POSITION_KEY_TO_TYPE``) at
       all -- never generated because there is nothing to generate from.
       Includes Regional Director/other national-level roles not tied to a
       ``UserRoleChange`` term (RD is assigned via ``Region.directors``, not
       a role change with a start/end date -- see the RD-specific branch
       below), so they get a distinct explanation, not the generic one.
    2. Every current in-scope role resolves to "excluded" (per-position
       override, or its type's Config flag off) -- never generated because
       ``generate_obligations`` skips excluded positions entirely.
    3. Otherwise: at least one current in-scope role is required/optional,
       but its term end is too far away yet for the lookahead window to
       have reached it -- simply too early.

    Returns a plain sentence; callers should only show it when there truly
    are no obligations to display.
    """
    today = timezone.now().date()
    current_role_changes = list(
        UserRoleChange.objects.filter(user=user, role__in=list(POSITION_KEY_TO_TYPE), end__gte=today).order_by("end")
    )
    if not current_role_changes:
        if user.director_regions.exists() or user.is_national_officer_group:
            return (
                "Your national-level role does not have its own Transition Report in this system. "
                "Use the Search reports section below to read what your chapters have submitted."
            )
        return "You don't currently hold a position that requires a Transition Report."

    excluded_status = PositionOverride.Status.excluded.name
    eligible = [rc for rc in current_role_changes if resolve_position_status(rc.role) != excluded_status]
    if not eligible:
        return "Your current position does not require a Transition Report."

    soonest = min(eligible, key=lambda rc: rc.end)
    due_date = soonest.end - datetime.timedelta(days=get_due_date_offset_days())
    return (
        f"Not due yet: your {soonest.role.title()} term ends {soonest.end}, "
        f"so the report isn't due until {due_date}."
    )


def get_my_reports(user):
    """The viewer's own authored reports (draft + submitted), for the Transitions list."""
    return TransitionReport.objects.filter(author=user).select_related("chapter", "obligation").order_by("-created")


def get_or_create_report(obligation):
    """The obligation's ``TransitionReport``, creating a fresh draft if none exists.

    Fixed invariant: ``report.author == obligation.officer`` always -- only the
    assigned officer ever composes their own obligation; see
    ``views.ComposeReportView`` for the access check enforcing this.
    """
    template = resolve_template(obligation.position_key)
    report, _created = TransitionReport.objects.get_or_create(
        obligation=obligation,
        defaults={
            "chapter": obligation.chapter,
            "position_type": obligation.position_type,
            "position_key": obligation.position_key,
            "author": obligation.officer,
            "template": template,
            "template_version": template.version if template else 1,
        },
    )
    return report


def _save_answers(report, answers_data):
    for prompt, value in answers_data:
        ReportAnswer.objects.update_or_create(
            report=report,
            prompt_key=prompt.prompt_key,
            defaults={"prompt": prompt, "prompt_label_snapshot": prompt.label, "value": value},
        )


def save_draft(report, answers_data):
    """Persist answers without changing ``report.status`` -- draft saves never
    enforce required/min/max (that's ``submit_report``'s job); the form itself
    skips those checks when not submitting.
    """
    _save_answers(report, answers_data)
    report.save(update_fields=["modified"])
    return report


def submit_report(report, answers_data):
    """Write answers, stamp the template version actually used, and close the
    obligation. ``template_version`` is re-resolved here (not fixed at draft
    creation) so it always reflects what was current AT SUBMISSION, per the
    spec's "version used at submission" wording.
    """
    _save_answers(report, answers_data)
    template = resolve_template(report.position_key)
    if template is not None:
        report.template = template
        report.template_version = template.version
    report.status = TransitionReport.Status.submitted.value[0]
    report.submitted_at = timezone.now()
    report.save()
    derive_prompt_tags(report)
    report.obligation.status = ReportObligation.Status.submitted.value[0]
    report.obligation.save(update_fields=["status"])
    return report


def can_close_na_vacant(user, obligation):
    """Whether ``user`` may close ``obligation`` as na_vacant: the obligation
    chapter's current Regent, or a Regional Director for its region.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.current_chapter is not None and user.current_chapter.pk == obligation.chapter_id:
        if REGENT_ROLE_KEY in (user.current_roles or []):
            return True
    return user.director_regions.filter(pk=obligation.chapter.region_id).exists()


def get_vacant_obligations_for_closer(user):
    """Open, officer-less obligations ``user`` may close as na_vacant.

    A vacant obligation (``officer=None``) never appears in
    ``get_my_obligations`` (which filters by ``officer=user``), so it needs
    its own narrow, self-contained scope here: the Regent's own chapter, or
    an RD's own region. Deliberately NOT the full "reports I'm entitled to
    read" surface (that needs TRWI-6) -- just enough to make the na_vacant
    path usable now, per TRWI-5's own acceptance criterion.
    """
    open_status = ReportObligation.Status.open.value[0]
    if user.current_chapter is not None and REGENT_ROLE_KEY in (user.current_roles or []):
        return ReportObligation.objects.filter(
            chapter=user.current_chapter, officer__isnull=True, status=open_status
        ).select_related("chapter")
    director_regions = user.director_regions.all()
    if director_regions:
        return ReportObligation.objects.filter(
            chapter__region__in=director_regions, officer__isnull=True, status=open_status
        ).select_related("chapter")
    return ReportObligation.objects.none()


def close_as_na_vacant(obligation):
    obligation.status = ReportObligation.Status.na_vacant.value[0]
    obligation.save(update_fields=["status"])


# ---------------------------------------------------------------------------
# TRWI-6: access control service
# ---------------------------------------------------------------------------
# "Regional director" is excluded: RD already has its own, narrower,
# region-based scope in get_readable_reports, so the generic "same
# position_key, any chapter" rule below must not ALSO apply to it (that
# would let an RD see every OTHER region's RD reports too).
NATIONAL_OFFICER_SCOPED = NATIONAL_OFFICER - {"regional director"}


def get_readable_reports(user, **filters):
    """Every ``TransitionReport`` ``user`` is entitled to read (TRWI-6).

    The one centralized access-rule service -- every read surface (the
    Transitions list, TRWI-7's handoff packet, TRWI-8's prior-answers view,
    TRWI-9's dashboards, TRWI-11's search) must call this rather than
    re-deriving access.

    - **Author:** always their own report, draft or submitted. There is no
      approval step, but a draft is not "submitted and immediately visible"
      yet (see the Design decisions section), so every OTHER rule below only
      ever matches ``submitted`` reports -- nobody but the author previews an
      in-progress draft.
    - **Successor:** the current holder of position_key P reads every
      submitted P report for their own chapter -- full history, since
      nothing is archived (TRWI-10).
    - **Regent:** every position's submitted reports for their own chapter.
    - **RD:** every submitted report for chapters in their own region, via
      the existing ``user.director_regions`` (same pattern as
      ``awards/eligibility.py``'s regional scoping) -- no new region-scope
      lookup.
    - **Council ("Grand" officers) or Admin:** every submitted report,
      nationally. 2026-09 tightened this from "any National Officer" --
      seeing every chapter's full candor was broader than intended for a
      plain ``NATIONAL_OFFICER`` role (e.g. a candidate chapter director);
      only ``core.models.COUNCIL`` (the "Grand X" positions + council
      delegate) plus Admin see everything now. ``is_national_officer_group``
      is still checked alongside ``is_council_officer()`` so a Council
      member who has toggled "Hide national officer functionality"
      (``natoff_hidden``) previews as a regular member here too, same as
      everywhere else that toggle applies.
    - **Other National Officer (in ``NATIONAL_OFFICER``, not Council, not
      RD):** every submitted report for the SAME national-officer
      position_key they currently hold, across every chapter -- "reports
      related to them," not everything. Excludes "regional director"
      specifically: RD already has its own, narrower, region-based scope
      just above, and adding the bare position_key here too would widen an
      RD to see every OTHER region's RD reports as well, which the RD rule
      deliberately does not do.

    ``**filters`` apply on top of the rules above (e.g. ``position_key=...``)
    -- they narrow, never widen, what the rules already allow.
    """
    if not getattr(user, "is_authenticated", False):
        return TransitionReport.objects.none()

    base = TransitionReport.objects.select_related("chapter", "chapter__region", "obligation")
    submitted = Q(status=TransitionReport.Status.submitted.value[0])

    if user.is_admin or (user.is_national_officer_group and user.is_council_officer()):
        return base.filter(Q(author=user) | submitted, **filters)

    current_chapter = user.current_chapter
    current_roles = user.current_roles or []
    scope = Q()
    has_scope = False
    if current_chapter is not None:
        scope |= Q(chapter=current_chapter, position_key__in=current_roles)
        has_scope = True
        if REGENT_ROLE_KEY in current_roles:
            scope |= Q(chapter=current_chapter)
    director_regions = user.director_regions.all()
    if director_regions:
        scope |= Q(chapter__region__in=director_regions)
        has_scope = True
    if user.is_national_officer_group:
        other_national_roles = NATIONAL_OFFICER_SCOPED & set(current_roles)
        if other_national_roles:
            scope |= Q(position_key__in=other_national_roles)
            has_scope = True

    conditions = Q(author=user)
    if has_scope:
        # AND, not OR: everyone else's access is submitted-only (see above);
        # an empty `scope` (has_scope=False) is never ANDed in, since an
        # empty Q() would otherwise act as "always true" and leak every
        # submitted report to everyone.
        conditions |= submitted & scope
    return base.filter(conditions, **filters)


def can_read_report(user, report):
    """Whether ``user`` may read ``report`` (TRWI-6).

    Delegates to ``get_readable_reports`` -- "can I read this one" is just
    "is it in my readable queryset" -- so the two rule sets can never drift
    apart.
    """
    return get_readable_reports(user, pk=report.pk).exists()


# ---------------------------------------------------------------------------
# TRWI-7: successor handoff packet & acknowledgment
# ---------------------------------------------------------------------------
def get_handoff_packet(user, chapter, position_key):
    """ALL PREDECESSOR reports ``user`` may read for ``position_key`` in
    ``chapter`` (TRWI-7), reverse-chronological (``TransitionReport.Meta.
    ordering``). Excludes ``user``'s own report -- "predecessor reports" per
    the spec, not a mirror of their own in-progress/submitted one.

    Otherwise just ``get_readable_reports`` scoped down to one slot -- there
    is no separate access rule for the packet; it's the same TRWI-6 service
    every other read surface uses.
    """
    return get_readable_reports(user, chapter=chapter, position_key=position_key).exclude(author=user)


def acknowledge_report(report, user):
    """Record ``user`` having read ``report`` (TRWI-7). Idempotent -- a
    second acknowledgment of the same report by the same user is a no-op,
    matching the ``(report, user)`` unique constraint. Editing the report
    later does NOT reset or re-require acknowledgment (decision 2026-09-04).
    """
    ReportAcknowledgement.objects.get_or_create(report=report, user=user)


def send_handoff_notices(dry_run=False):
    """New-officeholder "predecessor reports are available" notice (TRWI-7).

    Fires once per ``UserRoleChange`` taking an in-scope, required/optional
    position, scanning the same ``LOOKBACK_GRACE_DAYS`` window as
    ``generate_obligations``' own trigger 1 -- so a historical data import
    can never flood years-old alumni with notices. Skips the actual SEND
    when there is nothing readable yet (an empty "here's your packet!" email
    is noise, not a nudge), but still records ``HandoffNotice`` either way so
    the role change is never re-evaluated once handled.

    Uses ``role_change.user.chapter`` (not ``user.current_chapter``) for the
    same reason ``generate_obligations`` does: the report/obligation rows
    this notice is about are keyed to the chapter actually held AT THE TIME,
    which for a National Officer with an active ``UserAlter`` preview
    override can differ from ``current_chapter``.

    ``dry_run`` skips every send/write explicitly, matching
    ``send_due_date_reminders``' reasoning (an actual email send is a real
    external side effect a rolled-back transaction can't undo). Returns the
    count of notices sent (or that would be sent, under ``dry_run``).
    """
    today = timezone.now().date()
    window_start = today - datetime.timedelta(days=LOOKBACK_GRACE_DAYS)
    sent = 0

    role_changes = UserRoleChange.objects.filter(
        role__in=list(POSITION_KEY_TO_TYPE),
        start__lte=today,
        end__gte=today,
        start__gte=window_start,
        transition_handoff_notice__isnull=True,
    ).select_related("user", "user__chapter")
    for role_change in role_changes:
        status = resolve_position_status(role_change.role)
        if status not in (PositionOverride.Status.required.name, PositionOverride.Status.optional.name):
            continue
        user = role_change.user
        chapter = user.chapter
        report_count = get_handoff_packet(user, chapter, role_change.role).count()
        if report_count > 0:
            if not dry_run:
                HandoffPacketAvailable(user, role_change.role, chapter, report_count).send()
            sent += 1
        if not dry_run:
            HandoffNotice.objects.create(role_change=role_change)

    return sent


# ---------------------------------------------------------------------------
# TRWI-8: prior answers while composing
# ---------------------------------------------------------------------------
def get_prior_answers(user, report):
    """``{prompt_key: ReportAnswer}`` of the MOST RECENT predecessor's answer
    to each of ``report``'s own current template's prompts (TRWI-8) --
    display only, never used to pre-fill anything.

    "The previous holder's answer" (singular, per the spec) means the single
    most recent predecessor report, not a merge scanning further back --
    ``get_handoff_packet`` is already most-recent-first and already excludes
    ``user``'s own report. Matched primarily by ``prompt_key``; falls back to
    ``prompt_label_snapshot`` for a prompt whose key changed since (a
    defensive fallback -- shipped keys are meant to stay immutable, F16).

    Respects TRWI-6 access rules automatically: if ``user`` doesn't qualify
    as a reader for this exact position/chapter (e.g. editing their own
    report long after current_roles no longer lists this position -- see
    decision F15), ``get_handoff_packet`` returns nothing and this returns
    ``{}``, same as if there were no predecessor reports at all.
    """
    if report.template is None:
        return {}
    predecessor = get_handoff_packet(user, report.chapter, report.position_key).first()
    if predecessor is None:
        return {}

    predecessor_answers = list(predecessor.answers.all())
    by_key = {answer.prompt_key: answer for answer in predecessor_answers}
    by_label = {answer.prompt_label_snapshot: answer for answer in predecessor_answers}

    prior_answers = {}
    for prompt in report.template.prompts.all():
        answer = by_key.get(prompt.prompt_key) or by_label.get(prompt.label)
        if answer is not None:
            prior_answers[prompt.prompt_key] = answer
    return prior_answers


# ---------------------------------------------------------------------------
# TRWI-9: compliance dashboards
# ---------------------------------------------------------------------------
# A "cycle" is one academic year (July-to-July, reusing
# core.models.academic_encompass_start_end_date -- the same calendar TRWI-4's
# seasonal reminder already anchors to). Kept to 3 fixed choices rather than a
# dynamically-enumerated list of every historical cycle -- "current" satisfies
# TRWI-9's own "current-cycle obligations" wording for the chapter view, and
# switching to "previous" is how "trend across cycles" is surfaced for the
# rates view, without needing an extra distinct-values query per request.
CYCLE_CHOICES = [
    ("current", "Current cycle"),
    ("previous", "Previous cycle"),
    ("all", "All time"),
]
DEFAULT_CYCLE = "current"


def get_cycle_bounds(cycle=DEFAULT_CYCLE, today=None):
    """``(start_date, end_date)`` for ``cycle``, or ``(None, None)`` for "all
    time" -- both plain ``datetime.date`` (not datetime), ready to compare
    against ``ReportObligation.due_date``.
    """
    today = today or timezone.now()
    if cycle == "all":
        return None, None
    start, end = academic_encompass_start_end_date(today)
    if cycle == "previous":
        start, end = academic_encompass_start_end_date(start - datetime.timedelta(days=1))
    return start.date(), end.date()


def cycle_label(cycle=DEFAULT_CYCLE, today=None):
    """Human-readable label for ``cycle``, e.g. "2025-2026" or "All time"."""
    start, end = get_cycle_bounds(cycle, today=today)
    if start is None:
        return "All time"
    return f"{start.year}-{end.year}"


@dataclass
class ChapterComplianceStats:
    """One chapter's obligation counts for a cycle (TRWI-9) -- submission and
    acknowledgment rate share the SAME denominator (``total`` obligations in
    the cycle), so the two percentages are directly comparable side by side.
    """

    chapter: object
    total: int
    submitted: int
    missed: int
    acknowledged: int

    @property
    def submission_rate(self):
        """Percent submitted, or ``None`` if there were no obligations at all."""
        if not self.total:
            return None
        return round(self.submitted / self.total * 100, 1)

    @property
    def acknowledgment_rate(self):
        """Percent whose report has at least one acknowledgment, or ``None``
        if there were no obligations at all.
        """
        if not self.total:
            return None
        return round(self.acknowledged / self.total * 100, 1)


def get_chapter_compliance_stats(chapters, cycle=DEFAULT_CYCLE, position_key=""):
    """``[ChapterComplianceStats, ...]``, one row per chapter in ``chapters``
    (TRWI-9 regional/national rates views).

    Exactly 2 aggregate queries total, regardless of how many chapters are
    passed in (``.values("chapter_id").annotate(...)``, not one query per
    chapter) -- the acknowledgment count is deliberately a SEPARATE query from
    the status counts: it joins through ``report__acknowledgements`` (a
    fan-out-prone reverse relation, since one report can have multiple
    acknowledgments), and Django's docs warn that combining a fan-out
    aggregate with other aggregates in the SAME query silently inflates them
    all unless every one of them is also ``distinct=True`` -- splitting into
    two single-purpose queries sidesteps that correctness trap entirely
    rather than trying to get multiple ``distinct=True`` aggregates exactly
    right in one query.
    """
    chapters = list(chapters)
    chapter_by_id = {chapter.pk: chapter for chapter in chapters}
    obligations = ReportObligation.objects.filter(chapter_id__in=chapter_by_id)
    start, end = get_cycle_bounds(cycle)
    if start is not None:
        obligations = obligations.filter(due_date__gte=start, due_date__lt=end)
    if position_key:
        obligations = obligations.filter(position_key=position_key)

    counts_by_chapter = {
        row["chapter_id"]: row
        for row in obligations.values("chapter_id").annotate(
            total=Count("id"),
            submitted=Count("id", filter=Q(status=ReportObligation.Status.submitted.value[0])),
            missed=Count("id", filter=Q(status=ReportObligation.Status.missed.value[0])),
        )
    }
    acks_by_chapter = {
        row["chapter_id"]: row["acknowledged"]
        for row in obligations.values("chapter_id").annotate(
            acknowledged=Count("id", filter=Q(report__acknowledgements__isnull=False), distinct=True)
        )
    }

    return [
        ChapterComplianceStats(
            chapter=chapter,
            total=counts_by_chapter.get(chapter.pk, {}).get("total", 0),
            submitted=counts_by_chapter.get(chapter.pk, {}).get("submitted", 0),
            missed=counts_by_chapter.get(chapter.pk, {}).get("missed", 0),
            acknowledged=acks_by_chapter.get(chapter.pk, 0),
        )
        for chapter in chapters
    ]


def can_view_chapter_dashboard(user, chapter):
    """Whether ``user`` may view ``chapter``'s compliance dashboard (TRWI-9).

    National Officer/Admin: any chapter. RD: any chapter in their own
    region(s) (``user.director_regions``, TRWI-6's existing RD pattern).
    Otherwise: only their OWN chapter, and only if they're an officer of
    SOME kind (``is_officer_group``) -- matches TRWI-9's own "Chapter view
    (Regent/officers)" scoping; a plain member never sees this page, even
    for their own chapter.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_admin or user.is_national_officer_group:
        return True
    if user.director_regions.filter(pk=chapter.region_id).exists():
        return True
    return user.chapter_id == chapter.pk and user.is_officer_group


def can_view_compliance_rates(user):
    """Whether ``user`` may view the regional/national rates dashboard
    (TRWI-9) -- RD/CCD (CCD is a plain national officer, decision 2026-09-04)
    or National Officer/Admin. Deliberately excludes plain chapter officers:
    a single-chapter rate is less useful to them than the Chapter view's own
    per-obligation detail.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return user.is_admin or user.is_national_officer_group or user.director_regions.exists()


def get_compliance_rate_chapters(user, region=None):
    """Active chapters ``user``'s rates dashboard should cover (TRWI-9).

    National Officer/Admin: every active chapter, optionally narrowed to one
    ``region``. RD: only their own ``director_regions``' chapters -- the
    ``region`` param is ignored for an RD, since their own scope is already
    narrower than any single region they'd pick.
    """
    chapters = Chapter.objects.filter(active=True)
    if user.is_admin or user.is_national_officer_group:
        if region is not None:
            chapters = chapters.filter(region=region)
        return chapters.select_related("region").order_by("name")
    return chapters.filter(region__in=user.director_regions.all()).select_related("region").order_by("name")


# ---------------------------------------------------------------------------
# TRWI-11: search & national trend view
# ---------------------------------------------------------------------------
def derive_prompt_tags(report):
    """(Re-)derive ``report``'s ``source="prompt"`` tags from
    ``TemplatePrompt.tag`` (TRWI-11): one tag per DISTINCT non-blank
    ``TemplatePrompt.tag`` among the prompts ``report`` actually answered
    (non-blank ``ReportAnswer.value``) on its own current ``template``.

    Called from ``submit_report`` -- always fully re-derived (existing
    ``source="prompt"`` rows deleted first) so a later re-submit with
    different answers never leaves a stale tag behind. Never touches
    ``source="manual"`` rows -- ``set_manual_tags`` owns those exclusively.
    """
    report.tags.filter(source=ReportTag.Source.prompt.value[0]).delete()
    if report.template is None:
        return
    answered_keys = set(report.answers.exclude(value="").values_list("prompt_key", flat=True))
    tag_by_prompt_key = {prompt.prompt_key: prompt.tag for prompt in report.template.prompts.all() if prompt.tag}
    tags = {tag_by_prompt_key[key] for key in answered_keys if key in tag_by_prompt_key}
    for tag in tags:
        ReportTag.objects.get_or_create(report=report, tag=tag, defaults={"source": ReportTag.Source.prompt.value[0]})


def set_manual_tags(report, tags):
    """Replace ``report``'s ``source="manual"`` tags with ``tags`` (an
    iterable of ``TransitionTag.name`` values, not restricted to
    ``TAG_CHOICES`` since the 2026-09 "Additional tags" autocomplete change --
    see ``forms.ComposeReportForm.manual_tags_data``). Leaves any
    ``source="prompt"`` rows untouched -- the author's own additions are
    independent of whatever ``derive_prompt_tags`` derives from their
    answers.
    """
    report.tags.filter(source=ReportTag.Source.manual.value[0]).delete()
    for tag in tags:
        ReportTag.objects.get_or_create(report=report, tag=tag, defaults={"source": ReportTag.Source.manual.value[0]})


def search_reports(user, query="", position_key="", chapter=None, region=None, tag="", cycle=DEFAULT_CYCLE):
    """Full-text + filtered search across every ``TransitionReport`` ``user``
    may read (TRWI-11).

    ``get_readable_reports`` (TRWI-6) is the base queryset -- search can
    never surface a report the viewer couldn't otherwise open; access rules
    and search share the one enforcement point, exactly like every other
    read surface. Restricted to ``submitted`` reports regardless of author --
    a draft-in-progress isn't "institutional knowledge" yet, and the author
    is already looking at it in the compose view (passing ``status=`` as an
    extra filter narrows the author's own OR-branch down too, not just the
    successor/Regent/RD/national branch that's already submitted-only).

    ``query`` (if given) narrows by full-text relevance via ``watson.filter``
    against the ``TransitionReport`` watson index (registered in
    ``TransitionsConfig.ready``, over the report's own answer text plus
    chapter/author identity) -- ranked, and applied ON TOP OF the
    already-access-scoped queryset rather than a bare global search. An
    empty ``query`` just returns the filtered-but-unranked queryset (e.g.
    "every Regent report tagged 'risk' this cycle", no keywords needed).
    """
    queryset = get_readable_reports(user, status=TransitionReport.Status.submitted.value[0]).prefetch_related("tags")
    if position_key:
        queryset = queryset.filter(position_key=position_key)
    if chapter is not None:
        queryset = queryset.filter(chapter=chapter)
    if region is not None:
        queryset = queryset.filter(chapter__region=region)
    if tag:
        queryset = queryset.filter(tags__tag=tag)
    start, end = get_cycle_bounds(cycle)
    if start is not None:
        queryset = queryset.filter(submitted_at__date__gte=start, submitted_at__date__lt=end)
    if query:
        queryset = watson.filter(queryset, query)
    return queryset


@dataclass
class ReportRow:
    """One row of the combined "Search reports" table (2026-09 UI pass).

    Either a submitted report the viewer may read (``person`` is the
    author, plus tags/submitted date/a link out) or -- when the search is
    narrowed to one ``chapter`` -- a ``ReportObligation`` with no readable
    report yet (``person`` is the officer or "Vacant", status/due date
    only). Replaces what used to be two separate tables (the search
    results table and the chapter compliance/obligation table).
    """

    position_key: str
    chapter_name: str
    person: str
    status: str
    status_display: str
    due_date: object = None
    submitted_at: object = None
    acknowledged: object = None
    tag_list: str = ""
    link_url: object = None


def _report_row(report, user, acknowledged):
    if report.author_id == user.pk:
        link_url = reverse("transitions:compose", args=[report.obligation.public_id])
    else:
        link_url = reverse("transitions:packet", args=[report.chapter_id, report.position_key])
    return ReportRow(
        position_key=report.position_key,
        chapter_name=report.chapter.name,
        person=report.author.name,
        status="submitted",
        status_display=report.get_status_display(),
        due_date=report.obligation.due_date,
        submitted_at=report.submitted_at,
        acknowledged=acknowledged,
        tag_list=report.tag_list,
        link_url=link_url,
    )


def _obligation_row(obligation, chapter_name, user):
    link_url = None
    if obligation.status in ("open", "missed") and obligation.officer_id == user.pk:
        link_url = reverse("transitions:compose", args=[obligation.public_id])
    return ReportRow(
        position_key=obligation.position_key,
        chapter_name=chapter_name,
        person=obligation.officer.name if obligation.officer_id else "Vacant",
        status=obligation.status,
        status_display=obligation.get_status_display(),
        due_date=obligation.due_date,
        link_url=link_url,
    )


def get_report_rows(user, query="", position_key="", chapter=None, region=None, tag="", cycle=DEFAULT_CYCLE):
    """Combined rows for the merged "Search reports" table (2026-09 UI pass).

    Always includes every submitted report ``user`` may read
    (``search_reports``, same filters, any chapter within their read
    scope). When ``chapter`` narrows the search to one specific chapter,
    ALSO adds a row for every OTHER obligation in that chapter with no
    readable report yet (open/missed/na_vacant, or submitted but not one
    ``user`` may read) -- so nothing the old, separate chapter compliance
    table used to show is lost, just merged into one row set, deduplicated
    by obligation (``exclude(pk__in=covered_obligation_ids)``).
    """
    reports = list(
        search_reports(
            user, query=query, position_key=position_key, chapter=chapter, region=region, tag=tag, cycle=cycle
        ).select_related("author", "chapter", "obligation")
    )
    acknowledged_report_ids = set(
        ReportAcknowledgement.objects.filter(report_id__in=[report.pk for report in reports]).values_list(
            "report_id", flat=True
        )
    )
    rows = [_report_row(report, user, report.pk in acknowledged_report_ids) for report in reports]

    if chapter is not None:
        covered_obligation_ids = {report.obligation_id for report in reports}
        obligations = (
            ReportObligation.objects.filter(chapter=chapter)
            .exclude(pk__in=covered_obligation_ids)
            .select_related("officer")
        )
        if position_key:
            obligations = obligations.filter(position_key=position_key)
        start, end = get_cycle_bounds(cycle)
        if start is not None:
            obligations = obligations.filter(due_date__gte=start, due_date__lt=end)
        rows += [_obligation_row(obligation, chapter.name, user) for obligation in obligations]

    return rows


def get_tag_frequency(cycle=DEFAULT_CYCLE, position_key="", region=None):
    """``[{"tag", "tag_label", "count"}, ...]``, most common first, across
    every submitted report matching the given filters (TRWI-11 national
    trend view) -- deliberately NOT scoped through ``get_readable_reports``:
    this is a National Officer/Admin-only surface that already sees every
    submitted report, gated at the view level by ``can_view_trends``, not
    filtered per-viewer here.

    The "failure" tag's own count/rank here IS the "most common failure
    themes" signal (TRWI-11's acceptance criterion) -- v1 is a deterministic
    controlled-vocabulary count, not free-text theme extraction/summarization.
    """
    reports = TransitionReport.objects.filter(status=TransitionReport.Status.submitted.value[0])
    start, end = get_cycle_bounds(cycle)
    if start is not None:
        reports = reports.filter(submitted_at__date__gte=start, submitted_at__date__lt=end)
    if position_key:
        reports = reports.filter(position_key=position_key)
    if region is not None:
        reports = reports.filter(chapter__region=region)

    tag_labels = dict(TAG_CHOICES)
    counts = (
        ReportTag.objects.filter(report__in=reports).values("tag").annotate(count=Count("id")).order_by("-count", "tag")
    )
    return [
        {"tag": row["tag"], "tag_label": tag_labels.get(row["tag"], row["tag"]), "count": row["count"]}
        for row in counts
    ]


def get_chapters_with_no_submissions(cycle=DEFAULT_CYCLE, position_key="", region=None):
    """Active chapters with ZERO submitted ``TransitionReport``s matching the
    given filters (TRWI-11 national trend view) -- the flip side of
    ``get_tag_frequency``: which chapters have nothing to mine yet.
    """
    submitted = TransitionReport.objects.filter(status=TransitionReport.Status.submitted.value[0])
    start, end = get_cycle_bounds(cycle)
    if start is not None:
        submitted = submitted.filter(submitted_at__date__gte=start, submitted_at__date__lt=end)
    if position_key:
        submitted = submitted.filter(position_key=position_key)
    chapters_with_reports = submitted.values_list("chapter_id", flat=True)
    chapters = Chapter.objects.filter(active=True).exclude(pk__in=chapters_with_reports)
    if region is not None:
        chapters = chapters.filter(region=region)
    return chapters.select_related("region").order_by("name")


def can_view_trends(user):
    """Whether ``user`` may view the national tag-trend view (TRWI-11) --
    National Officer/Admin only. Deliberately narrower than
    ``can_view_compliance_rates`` (no RD branch): trends mine free-text
    content across ALL chapters/positions at once, a more sensitive surface
    than a single region's numeric submission rate.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    return user.is_admin or user.is_national_officer_group
