from thetatauCMT.configs.models import Config

from .models import PositionOverride, PositionType, ReportTemplate, position_type_for_key

DUE_DATE_OFFSET_DAYS_CONFIG_KEY = "TRANSITIONS_DUE_DATE_OFFSET_DAYS"
REMINDER_OFFSETS_DAYS_CONFIG_KEY = "TRANSITIONS_REMINDER_OFFSETS_DAYS"
SEASONAL_REMINDER_OFFSET_DAYS_CONFIG_KEY = "TRANSITIONS_SEASONAL_REMINDER_OFFSET_DAYS"

DEFAULT_DUE_DATE_OFFSET_DAYS = 14
DEFAULT_REMINDER_OFFSETS_DAYS = (21, 14, 7, 1, -1, -7, -14)
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
