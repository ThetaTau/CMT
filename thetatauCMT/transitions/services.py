import datetime

from django.db import transaction
from django.utils import timezone

from core.models import CHAPTER_OFFICER_REQUIRED, semester_encompass_start_end_date
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.configs.models import Config
from thetatauCMT.users.models import User, UserRoleChange

from .models import (
    POSITION_KEY_TO_TYPE,
    PositionOverride,
    PositionType,
    ReportObligation,
    ReportTemplate,
    position_type_for_key,
)
from .notifications import TransitionReportDueReminder, TransitionReportSeasonalReminder

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
