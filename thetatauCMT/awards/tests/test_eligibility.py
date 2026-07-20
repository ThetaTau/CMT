import pytest

from thetatauCMT.awards.eligibility import (
    get_eligible_recipients,
    is_eligible,
    register_eligibility_hook,
)
from thetatauCMT.awards.models import AwardType
from thetatauCMT.awards.tests.factories import AwardTypeFactory, EligibilityRuleFactory
from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

_NAMES = list(GREEK_ABR.values())

# A test-only pluggable hook, registered once at import time.
HOOK_CALLS = []


@register_eligibility_hook("awards_test_only_hook")
def _test_hook(queryset, *, award_type, cycle, actor, params):
    HOOK_CALLS.append(params)
    only_pk = params.get("only_pk")
    return queryset.filter(pk=only_pk) if only_pk is not None else queryset


def _chapter(name, region=None):
    chapter = ChapterFactory(name=name)
    if region is not None:
        chapter.region = region
        chapter.save(update_fields=["region"])
    return chapter


# ---------------------------------------------------------------------------
# recipient_kind property (level -> kind)
# ---------------------------------------------------------------------------
def test_recipient_kind_property():
    assert AwardTypeFactory(level="member").recipient_kind == "member"
    assert AwardTypeFactory(level="active").recipient_kind == "member"
    assert AwardTypeFactory(level="national").recipient_kind == "member"
    assert AwardTypeFactory(level="chapter").recipient_kind == "chapter"
    assert AwardTypeFactory(level="region").recipient_kind == "region"


def test_no_rules_all_of_kind_eligible():
    award = AwardTypeFactory(level="member")
    m1 = UserFactory(status="active")
    m2 = UserFactory(status="alumni")
    result = get_eligible_recipients(award)
    assert m1 in result
    assert m2 in result


# ---------------------------------------------------------------------------
# Acceptance: active-only rule excludes alumni
# ---------------------------------------------------------------------------
def test_active_only_rule_excludes_alumni():
    award = AwardTypeFactory(level="member")
    EligibilityRuleFactory(award_type=award, rule_type="member_status", member_status="active")
    active = UserFactory(status="active")
    alumni = UserFactory(status="alumni")
    result = get_eligible_recipients(award)
    assert active in result
    assert alumni not in result


# ---------------------------------------------------------------------------
# Acceptance: PNM eligibility
# ---------------------------------------------------------------------------
def test_pnm_eligibility():
    award = AwardTypeFactory(level="pnm")
    EligibilityRuleFactory(award_type=award, rule_type="member_status", member_status="pnm")
    pnm = UserFactory(status="pnm")
    active = UserFactory(status="active")
    result = get_eligible_recipients(award)
    assert pnm in result
    assert active not in result


# ---------------------------------------------------------------------------
# Acceptance: chapter / region scoping
# ---------------------------------------------------------------------------
def test_chapter_scope_restricts_members():
    chapter_a = _chapter(_NAMES[0])
    chapter_b = _chapter(_NAMES[1])
    member_a = UserFactory(chapter=chapter_a, status="active")
    member_b = UserFactory(chapter=chapter_b, status="active")
    award = AwardTypeFactory(level="member")
    rule = EligibilityRuleFactory(award_type=award, rule_type="chapter_scope")
    rule.chapters.set([chapter_a])
    result = get_eligible_recipients(award)
    assert member_a in result
    assert member_b not in result


def test_region_scope_restricts_members():
    region_a = RegionFactory()
    region_b = RegionFactory()
    chapter_a = _chapter(_NAMES[0], region_a)
    chapter_b = _chapter(_NAMES[1], region_b)
    member_a = UserFactory(chapter=chapter_a, status="active")
    member_b = UserFactory(chapter=chapter_b, status="active")
    award = AwardTypeFactory(level="member")
    rule = EligibilityRuleFactory(award_type=award, rule_type="region_scope")
    rule.regions.set([region_a])
    result = get_eligible_recipients(award)
    assert member_a in result
    assert member_b not in result


def test_chapter_award_with_chapter_scope():
    chapter_a = _chapter(_NAMES[0])
    chapter_b = _chapter(_NAMES[1])
    award = AwardTypeFactory(level="chapter")
    rule = EligibilityRuleFactory(award_type=award, rule_type="chapter_scope")
    rule.chapters.set([chapter_a])
    result = get_eligible_recipients(award)
    assert chapter_a in result
    assert chapter_b not in result
    assert is_eligible(award, chapter_a) is True


def test_region_award_with_region_scope():
    region_a = RegionFactory()
    region_b = RegionFactory()
    award = AwardTypeFactory(level="region")
    rule = EligibilityRuleFactory(award_type=award, rule_type="region_scope")
    rule.regions.set([region_a])
    result = get_eligible_recipients(award)
    assert region_a in result
    assert region_b not in result


# ---------------------------------------------------------------------------
# Acceptance: pluggable hook invoked
# ---------------------------------------------------------------------------
def test_custom_hook_invoked_and_filters():
    award = AwardTypeFactory(level="member")
    keep = UserFactory(status="active")
    drop = UserFactory(status="active")
    EligibilityRuleFactory(
        award_type=award,
        rule_type="custom_hook",
        hook_key="awards_test_only_hook",
        params={"only_pk": keep.pk},
    )
    HOOK_CALLS.clear()
    result = get_eligible_recipients(award)
    assert keep in result
    assert drop not in result
    assert len(HOOK_CALLS) == 1  # the hook was invoked exactly once


def test_unregistered_hook_key_is_ignored():
    award = AwardTypeFactory(level="member")
    member = UserFactory(status="active")
    EligibilityRuleFactory(award_type=award, rule_type="custom_hook", hook_key="does_not_exist")
    assert member in get_eligible_recipients(award)


# ---------------------------------------------------------------------------
# Acceptance: get_eligible_recipients respects actor role scope
# ---------------------------------------------------------------------------
def test_scope_chapter_officer_sees_only_own_chapter():
    chapter_a = _chapter(_NAMES[0])
    chapter_b = _chapter(_NAMES[1])
    member_a = UserFactory(chapter=chapter_a, status="active")
    member_b = UserFactory(chapter=chapter_b, status="active")
    actor = UserFactory(chapter=chapter_a)  # plain member, scoped to their chapter
    award = AwardTypeFactory(level="member")
    result = get_eligible_recipients(award, actor=actor)
    assert member_a in result
    assert member_b not in result


def test_scope_regional_director_sees_only_their_region():
    region = RegionFactory()
    other_region = RegionFactory()
    chapter_in = _chapter(_NAMES[0], region)
    chapter_out = _chapter(_NAMES[1], other_region)
    member_in = UserFactory(chapter=chapter_in, status="active")
    member_out = UserFactory(chapter=chapter_out, status="active")
    rd = UserFactory()
    region.directors.add(rd)
    award = AwardTypeFactory(level="member")
    result = get_eligible_recipients(award, actor=rd)
    assert member_in in result
    assert member_out not in result


def test_scope_national_officer_sees_all():
    chapter_a = _chapter(_NAMES[0])
    chapter_b = _chapter(_NAMES[1])
    member_a = UserFactory(chapter=chapter_a, status="active")
    member_b = UserFactory(chapter=chapter_b, status="active")
    natoff = UserFactory(is_superuser=True)
    award = AwardTypeFactory(level="member")
    result = get_eligible_recipients(award, actor=natoff)
    assert member_a in result
    assert member_b in result


# ---------------------------------------------------------------------------
# is_eligible single check
# ---------------------------------------------------------------------------
def test_is_eligible_single_check():
    award = AwardTypeFactory(level="member")
    EligibilityRuleFactory(award_type=award, rule_type="member_status", member_status="active")
    active = UserFactory(status="active")
    alumni = UserFactory(status="alumni")
    assert is_eligible(award, active) is True
    assert is_eligible(award, alumni) is False


def test_is_eligible_recipient_kind_mismatch():
    member_award = AwardTypeFactory(level=AwardType.Level.MEMBER)
    chapter = ChapterFactory(name=_NAMES[0])
    assert is_eligible(member_award, chapter) is False


def test_recipient_kind_guard_blocks_mismatched_kind():
    award = AwardTypeFactory(level="member")  # kind == member
    member = UserFactory(status="active")
    # a recipient_kind rule that only allows chapters -> members become ineligible
    EligibilityRuleFactory(award_type=award, rule_type="recipient_kind", params={"kind": "chapter"})
    assert member not in get_eligible_recipients(award)
