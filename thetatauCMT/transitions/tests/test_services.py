import pytest

from thetatauCMT.configs.models import Config

from .. import services
from ..models import PositionOverride, ReportTemplate

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# resolve_position_status / is_position_required
# ---------------------------------------------------------------------------
def test_chapter_officer_position_is_always_required():
    assert services.resolve_position_status("treasurer") == "required"
    assert services.is_position_required("treasurer") is True


def test_pledge_educator_and_risk_mgmt_chair_are_required_like_chapter_officers():
    assert services.resolve_position_status("pledge/new member educator") == "required"
    assert services.resolve_position_status("risk management chair") == "required"


def test_council_position_is_optional_by_default():
    assert services.resolve_position_status("grand regent") == "optional"
    assert services.is_position_required("grand regent") is False


def test_national_officer_position_is_optional_by_default():
    assert services.resolve_position_status("regional director") == "optional"


def test_committee_chair_position_is_optional_by_default():
    assert services.resolve_position_status("committee chair") == "optional"


def test_advisor_roles_and_unknown_keys_are_out_of_scope():
    assert services.resolve_position_status("adviser") is None
    assert services.resolve_position_status("not a real position") is None


def test_type_level_disable_excludes_optional_positions():
    Config.objects.create(key="TRANSITIONS_COUNCIL_ENABLED", value="off", description="")
    assert services.resolve_position_status("grand regent") == "excluded"
    # A different optional type is unaffected.
    assert services.resolve_position_status("regional director") == "optional"


def test_type_level_disable_never_affects_chapter_officer():
    Config.objects.create(key="TRANSITIONS_COUNCIL_ENABLED", value="off", description="")
    assert services.resolve_position_status("treasurer") == "required"


def test_per_position_override_wins_over_chapter_officer_default():
    PositionOverride.objects.create(position_key="treasurer", status="excluded")
    assert services.resolve_position_status("treasurer") == "excluded"


def test_per_position_override_wins_over_disabled_type():
    Config.objects.create(key="TRANSITIONS_COUNCIL_ENABLED", value="off", description="")
    PositionOverride.objects.create(position_key="grand regent", status="required")
    assert services.resolve_position_status("grand regent") == "required"


# ---------------------------------------------------------------------------
# Offset config -- defaults present, Config values parsed correctly
# ---------------------------------------------------------------------------
def test_offset_defaults_present_with_no_config_rows():
    assert services.get_due_date_offset_days() == services.DEFAULT_DUE_DATE_OFFSET_DAYS
    assert services.get_seasonal_reminder_offset_days() == services.DEFAULT_SEASONAL_REMINDER_OFFSET_DAYS
    assert services.get_reminder_offsets_days() == list(services.DEFAULT_REMINDER_OFFSETS_DAYS)


def test_offset_config_rows_are_parsed():
    Config.objects.create(key="TRANSITIONS_DUE_DATE_OFFSET_DAYS", value="21", description="")
    Config.objects.create(key="TRANSITIONS_SEASONAL_REMINDER_OFFSET_DAYS", value="45", description="")
    Config.objects.create(key="TRANSITIONS_REMINDER_OFFSETS_DAYS", value="30,15,-7,-14", description="")

    assert services.get_due_date_offset_days() == 21
    assert services.get_seasonal_reminder_offset_days() == 45
    assert services.get_reminder_offsets_days() == [30, 15, -7, -14]


def test_reminder_offsets_default_includes_past_due_escalation():
    # 21/14/7/1 before due, plus -1/-7/-14 after due for past-due escalation.
    assert services.get_reminder_offsets_days() == [21, 14, 7, 1, -1, -7, -14]


def test_offset_config_falls_back_on_unparsable_value():
    Config.objects.create(key="TRANSITIONS_DUE_DATE_OFFSET_DAYS", value="not a number", description="")
    assert services.get_due_date_offset_days() == services.DEFAULT_DUE_DATE_OFFSET_DAYS


# ---------------------------------------------------------------------------
# resolve_template -- 3-tier resolution (TRWI-2)
# ---------------------------------------------------------------------------
def test_resolve_template_out_of_scope_position_returns_none():
    assert services.resolve_template("adviser") is None
    assert services.resolve_template("not a real position") is None


def test_resolve_template_returns_none_when_nothing_is_seeded():
    assert services.resolve_template("treasurer") is None


def test_resolve_template_falls_back_to_type_default():
    type_default = ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    assert services.resolve_template("treasurer") == type_default
    # Any chapter_officer-type position resolves to the same type default.
    assert services.resolve_template("pledge/new member educator") == type_default


def test_resolve_template_prefers_exact_position_key_match():
    ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Chapter Officer Report")
    treasurer_specific = ReportTemplate.objects.create(
        position_type="CHAPTER_OFFICER", position_key="treasurer", name="Treasurer Report"
    )
    assert services.resolve_template("treasurer") == treasurer_specific
    # A sibling chapter_officer position still gets the type default.
    assert services.resolve_template("scribe").name == "Chapter Officer Report"


def test_resolve_template_falls_back_to_global_default():
    global_default = ReportTemplate.objects.create(position_type="", position_key="", name="Global Default")
    assert services.resolve_template("treasurer") == global_default
    assert services.resolve_template("grand regent") == global_default


def test_resolve_template_ignores_inactive_templates():
    ReportTemplate.objects.create(position_type="CHAPTER_OFFICER", name="Inactive", is_active=False)
    global_default = ReportTemplate.objects.create(position_type="", position_key="", name="Global Default")
    assert services.resolve_template("treasurer") == global_default
