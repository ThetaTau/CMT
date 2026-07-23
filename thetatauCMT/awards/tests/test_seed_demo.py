import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from thetatauCMT.awards.models import (
    AwardCycle,
    AwardGrant,
    AwardNominationProcess,
    AwardType,
    EligibilityRule,
    GrantArtifact,
    OfficerBadge,
)
from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.models import User
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

DEMO = "[DEMO] "
_NAMES = list(GREEK_ABR.values())


def _seed(**kwargs):
    kwargs.setdefault("force", True)
    call_command("seed_awards_demo", **kwargs)


def _demo_counts():
    return {
        "types": AwardType.objects.filter(name__startswith=DEMO).count(),
        "cycles": AwardCycle.objects.filter(name__startswith=DEMO).count(),
        "rules": EligibilityRule.objects.filter(award_type__name__startswith=DEMO).count(),
        "grants": AwardGrant.objects.filter(award_type__name__startswith=DEMO).count(),
        "noms": AwardNominationProcess.objects.filter(award_type__name__startswith=DEMO).count(),
        "artifacts": GrantArtifact.objects.filter(grant__award_type__name__startswith=DEMO).count(),
        "badges": OfficerBadge.objects.filter(short_label__startswith=DEMO).count(),
    }


# ---------------------------------------------------------------------------
# Runs cleanly on an empty DB + full feature coverage + model constraints
# ---------------------------------------------------------------------------
def test_seeds_full_coverage_on_empty_db():
    _seed(scale="small", seed=1)

    # Catalog: every level, plus a retired award.
    demo_types = AwardType.objects.filter(name__startswith=DEMO)
    assert demo_types.count() == 8
    assert set(demo_types.values_list("level", flat=True)) >= {
        "member",
        "chapter",
        "region",
        "alumni",
        "active",
        "pnm",
        "national",
    }
    assert demo_types.filter(is_active=False).exists()  # retired
    assert demo_types.filter(grant_method="direct").exists()
    assert demo_types.filter(grant_method="nomination_workflow").exists()

    # Cycles: each period type.
    demo_cycles = AwardCycle.objects.filter(name__startswith=DEMO)
    assert set(demo_cycles.values_list("period_type", flat=True)) == {"year", "term", "event"}

    # Eligibility rules across kinds.
    demo_rules = EligibilityRule.objects.filter(award_type__name__startswith=DEMO)
    assert set(demo_rules.values_list("rule_type", flat=True)) >= {
        "member_status",
        "chapter_scope",
        "region_scope",
        "custom_hook",
    }

    # Grants: every source, every recipient kind, backdated + revoked.
    demo_grants = AwardGrant.objects.filter(award_type__name__startswith=DEMO)
    assert {"direct", "nomination", "import"} <= set(demo_grants.values_list("source", flat=True))
    assert demo_grants.filter(recipient_member__isnull=False).exists()
    assert demo_grants.filter(recipient_chapter__isnull=False).exists()
    assert demo_grants.filter(recipient_region__isnull=False).exists()
    assert demo_grants.filter(effective_date__year=2019).exists()  # backdated
    assert demo_grants.filter(status="revoked").exists()
    # Group grant: multiple individual member grants in one cycle for one award.
    assert demo_grants.filter(recipient_member__isnull=False).count() >= 3

    # Exactly one recipient per grant (mirrors the DB constraint).
    for grant in demo_grants:
        assert grant._recipient_count() == 1

    # Single-winner awards never exceed one active winner per cycle.
    for award in demo_types.filter(single_winner=True):
        for cycle in demo_cycles:
            assert AwardGrant.objects.active().for_cycle(award, cycle).count() <= 1

    # Nominations in all three states.
    demo_noms = AwardNominationProcess.objects.filter(award_type__name__startswith=DEMO)
    assert demo_noms.filter(result="").exists()  # pending / in review
    assert demo_noms.filter(result="approved").exists()
    assert demo_noms.filter(result="rejected").exists()
    assert demo_noms.filter(result="approved", resulting_grant__isnull=False).exists()

    # Certificates: one generated + one uploaded.
    assert GrantArtifact.objects.filter(artifact_type="generated").exists()
    assert GrantArtifact.objects.filter(artifact_type="uploaded").exists()

    # Officer badges + a config-driven approver routing to a real user.
    assert OfficerBadge.objects.filter(short_label__startswith=DEMO).exists()
    from thetatauCMT.configs.models import Config

    assert Config.get_value("AwardApprover")


# ---------------------------------------------------------------------------
# Reuses existing members / chapters / regions
# ---------------------------------------------------------------------------
def test_reuses_existing_members():
    chapter = ChapterFactory(name=_NAMES[0])
    for _ in range(8):
        UserFactory(chapter=chapter, status="active")
    _seed(scale="small", seed=1)
    # No demo *members* created when enough real members exist to reuse.
    assert not User.objects.filter(username__startswith="demo-awards-member-").exists()
    assert AwardGrant.objects.filter(award_type__name__startswith=DEMO).exists()


# ---------------------------------------------------------------------------
# Idempotent: re-running (no flush) never duplicates
# ---------------------------------------------------------------------------
def test_rerun_without_flush_no_duplicates():
    _seed(scale="small", seed=5)
    before = _demo_counts()
    _seed(scale="small", seed=5)
    assert _demo_counts() == before


# ---------------------------------------------------------------------------
# --flush-awards yields a clean, consistent reseed (no duplicates / growth)
# ---------------------------------------------------------------------------
def test_flush_reseed_is_consistent():
    _seed(scale="small", seed=3)
    before = _demo_counts()
    member_names = sorted(
        User.objects.filter(username__startswith="demo-awards-member-").values_list("name", flat=True)
    )
    _seed(scale="small", seed=3, flush_awards=True)
    assert _demo_counts() == before  # identical structure, nothing duplicated
    after_names = sorted(User.objects.filter(username__startswith="demo-awards-member-").values_list("name", flat=True))
    assert after_names == member_names  # reproducible / stable member set

    # No orphans: every demo grant still has its award + cycle + exactly one recipient.
    for grant in AwardGrant.objects.filter(award_type__name__startswith=DEMO):
        assert grant.award_type_id and grant.cycle_id and grant._recipient_count() == 1


# ---------------------------------------------------------------------------
# Flush only touches demo awards data (not members / chapters / regions)
# ---------------------------------------------------------------------------
def test_flush_preserves_supporting_and_non_demo_data():
    _seed(scale="small", seed=2)
    members_before = User.objects.count()
    # A non-demo award must survive a flush.
    keep = AwardType.objects.create(name="Real Award", level="member")
    _seed(scale="small", seed=2, flush_awards=True)
    assert AwardType.objects.filter(pk=keep.pk).exists()
    assert User.objects.count() >= members_before  # demo members not deleted


# ---------------------------------------------------------------------------
# Refuses to run outside DEBUG without --force
# ---------------------------------------------------------------------------
def test_refuses_without_force(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_awards_demo")
