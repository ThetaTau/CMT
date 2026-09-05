import pytest

from core.models import ADVISOR_ROLES, CHAPTER_OFFICER_REQUIRED, COMMITTEE_CHAIR, COUNCIL, NATIONAL_OFFICER

from ..models import POSITION_KEY_CHOICES, PositionOverride, PositionType, position_type_for_key

pytestmark = pytest.mark.django_db


def test_position_key_choices_excludes_advisor_roles():
    keys = {key for key, _label in POSITION_KEY_CHOICES}
    assert keys.isdisjoint(ADVISOR_ROLES)


def test_position_key_choices_count_matches_core_models():
    # 7 CHAPTER_OFFICER_REQUIRED + 8 COUNCIL + 10 NATIONAL_OFFICER + 18 remaining
    # COMMITTEE_CHAIR (20 total minus the 2 already in CHAPTER_OFFICER_REQUIRED).
    expected = len(CHAPTER_OFFICER_REQUIRED | COUNCIL | NATIONAL_OFFICER | COMMITTEE_CHAIR)
    assert len(POSITION_KEY_CHOICES) == expected


def test_position_type_for_key_chapter_officer_positions():
    for key in CHAPTER_OFFICER_REQUIRED:
        assert position_type_for_key(key) == PositionType.chapter_officer


def test_position_type_for_key_pledge_educator_and_risk_mgmt_chair_are_chapter_officer():
    # These two are in core.models.COMMITTEE_CHAIR too, but decision B5 puts
    # them in the chapter_officer bucket (required, core prompt set).
    assert position_type_for_key("pledge/new member educator") == PositionType.chapter_officer
    assert position_type_for_key("risk management chair") == PositionType.chapter_officer


def test_position_type_for_key_council_and_national_officer():
    assert position_type_for_key("grand regent") == PositionType.council
    assert position_type_for_key("regional director") == PositionType.national_officer


def test_position_type_for_key_remaining_committee_chair():
    assert position_type_for_key("committee chair") == PositionType.committee_chair


def test_position_type_for_key_advisor_roles_are_out_of_scope():
    for key in ADVISOR_ROLES:
        assert position_type_for_key(key) is None


def test_position_type_for_key_unknown_key():
    assert position_type_for_key("not a real position") is None


def test_position_override_str():
    override = PositionOverride.objects.create(position_key="treasurer", status="excluded")
    assert str(override) == "treasurer (excluded)"


def test_position_override_position_key_is_unique():
    PositionOverride.objects.create(position_key="treasurer", status="excluded")
    with pytest.raises(Exception):
        PositionOverride.objects.create(position_key="treasurer", status="optional")
