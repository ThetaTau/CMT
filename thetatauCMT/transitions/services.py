import datetime

from django.db import transaction
from django.utils import timezone

from core.models import CHAPTER_OFFICER_REQUIRED
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.configs.models import Config
from thetatauCMT.users.models import UserRoleChange

from .models import (
    POSITION_KEY_TO_TYPE,
    PositionOverride,
    PositionType,
    ReportObligation,
    ReportTemplate,
    position_type_for_key,
)

DUE_DATE_OFFSET_DAYS_CONFIG_KEY = "TRANSITIONS_DUE_DATE_OFFSET_DAYS"
REMINDER_OFFSETS_DAYS_CONFIG_KEY = "TRANSITIONS_REMINDER_OFFSETS_DAYS"
SEASONAL_REMINDER_OFFSET_DAYS_CONFIG_KEY = "TRANSITIONS_SEASONAL_REMINDER_OFFSET_DAYS"

DEFAULT_DUE_DATE_OFFSET_DAYS = 14
DEFAULT_REMINDER_OFFSETS_DAYS = (21, 14, 7, 1, -1, -7, -14)

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
