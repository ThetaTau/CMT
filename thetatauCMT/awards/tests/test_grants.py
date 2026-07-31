import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from thetatauCMT.awards.models import AwardGrant, GrantAudit
from thetatauCMT.awards.services import (
    check_winner_allowed,
    count_active_winners,
    grant_award,
    grant_award_to_members,
    revoke_grant,
)
from thetatauCMT.awards.tests.factories import AwardCycleFactory, AwardGrantFactory, AwardTypeFactory
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Acceptance: grant to member / chapter / region
# ---------------------------------------------------------------------------
def test_grant_to_member():
    award = AwardTypeFactory.create()
    cycle = AwardCycleFactory.create()
    member = UserFactory.create()
    granter = UserFactory.create()
    grant = grant_award(award, cycle, member, granter, reason="Great work")
    assert grant.pk is not None
    assert grant.recipient_member_id == member.pk
    assert grant.recipient_chapter_id is None
    assert grant.recipient_region_id is None
    assert grant.recipient_kind == "member"
    assert grant.recipient == member
    assert grant.status == AwardGrant.Status.ACTIVE
    assert grant.source == AwardGrant.Source.DIRECT
    assert grant.reason == "Great work"


def test_grant_to_chapter():
    grant = grant_award(
        AwardTypeFactory.create(), AwardCycleFactory.create(), ChapterFactory.create(), UserFactory.create()
    )
    assert grant.recipient_chapter_id is not None
    assert grant.recipient_member_id is None
    assert grant.recipient_region_id is None
    assert grant.recipient_kind == "chapter"


def test_grant_to_region():
    grant = grant_award(
        AwardTypeFactory.create(), AwardCycleFactory.create(), RegionFactory.create(), UserFactory.create()
    )
    assert grant.recipient_region_id is not None
    assert grant.recipient_member_id is None
    assert grant.recipient_chapter_id is None
    assert grant.recipient_kind == "region"


def test_recipient_display_matches_recipient_str():
    member = UserFactory.create()
    grant = grant_award(AwardTypeFactory.create(name="Best"), AwardCycleFactory.create(), member, UserFactory.create())
    assert grant.recipient_display == str(member)
    assert "Best" in str(grant)
    assert str(member) in str(grant)


def test_unsupported_recipient_type_raises():
    with pytest.raises(ValueError):
        grant_award(AwardTypeFactory.create(), AwardCycleFactory.create(), "not-a-model", UserFactory.create())


# ---------------------------------------------------------------------------
# Acceptance: backdated effective_date
# ---------------------------------------------------------------------------
def test_backdated_effective_date():
    today = timezone.now().date()
    backdate = datetime.date(2015, 5, 1)
    grant = grant_award(
        AwardTypeFactory.create(),
        AwardCycleFactory.create(),
        UserFactory.create(),
        UserFactory.create(),
        effective_date=backdate,
        source=AwardGrant.Source.IMPORT,
    )
    assert grant.effective_date == backdate
    # granted_at stays the real system timestamp (today), not the backdate
    assert grant.granted_at.date() == today
    assert grant.source == AwardGrant.Source.IMPORT


def test_effective_date_defaults_to_today():
    grant = grant_award(
        AwardTypeFactory.create(), AwardCycleFactory.create(), UserFactory.create(), UserFactory.create()
    )
    assert grant.effective_date == timezone.now().date()


# ---------------------------------------------------------------------------
# Acceptance: revoke retains record + history
# ---------------------------------------------------------------------------
def test_revoke_retains_record_and_sets_fields():
    grant = AwardGrantFactory.create()
    revoker = UserFactory.create()
    revoke_grant(grant, revoker, reason="Rescinded")
    grant.refresh_from_db()
    assert grant.status == AwardGrant.Status.REVOKED
    assert grant.is_revoked is True
    assert grant.revoked_by_id == revoker.pk
    assert grant.revoked_at is not None
    assert grant.revoke_reason == "Rescinded"
    # never hard-deleted -- the row survives
    assert AwardGrant.objects.filter(pk=grant.pk).exists()


def test_revoke_is_idempotent():
    grant = AwardGrantFactory.create()
    revoker = UserFactory.create()
    revoke_grant(grant, revoker, reason="first")
    revoke_grant(grant, revoker, reason="second")  # no-op
    grant.refresh_from_db()
    assert grant.revoke_reason == "first"
    assert grant.audit_entries.filter(action=GrantAudit.Action.REVOKED).count() == 1


def test_active_and_revoked_querysets():
    active = AwardGrantFactory.create()
    revoked = AwardGrantFactory.create()
    revoke_grant(revoked, UserFactory.create())
    assert active in AwardGrant.objects.active()
    assert revoked not in AwardGrant.objects.active()
    assert revoked in AwardGrant.objects.revoked()


# ---------------------------------------------------------------------------
# Acceptance: group grant creates one grant per member
# ---------------------------------------------------------------------------
def test_group_grant_creates_one_grant_per_member():
    award = AwardTypeFactory.create()
    cycle = AwardCycleFactory.create()
    granter = UserFactory.create()
    members = [UserFactory.create() for _ in range(3)]
    grants = grant_award_to_members(award, cycle, members, granter, reason="Team award")
    assert len(grants) == 3
    assert {g.recipient_member_id for g in grants} == {m.pk for m in members}
    assert AwardGrant.objects.filter(award_type=award, cycle=cycle).count() == 3
    # each is an identical individual grant
    assert all(g.reason == "Team award" for g in grants)


# ---------------------------------------------------------------------------
# Acceptance: audit entries written
# ---------------------------------------------------------------------------
def test_audit_created_on_grant():
    grant = grant_award(
        AwardTypeFactory.create(), AwardCycleFactory.create(), UserFactory.create(), UserFactory.create()
    )
    entries = grant.audit_entries.all()
    assert entries.count() == 1
    entry = entries.first()
    assert entry.action == GrantAudit.Action.CREATED
    assert entry.detail["recipient_kind"] == "member"


def test_audit_uses_imported_action_for_import_source():
    grant = grant_award(
        AwardTypeFactory.create(),
        AwardCycleFactory.create(),
        UserFactory.create(),
        UserFactory.create(),
        source=AwardGrant.Source.IMPORT,
    )
    assert grant.audit_entries.first().action == GrantAudit.Action.IMPORTED


def test_audit_trail_records_created_then_revoked():
    grant = grant_award(
        AwardTypeFactory.create(), AwardCycleFactory.create(), UserFactory.create(), UserFactory.create()
    )
    revoke_grant(grant, UserFactory.create(), reason="x")
    actions = list(grant.audit_entries.values_list("action", flat=True))
    assert actions == [GrantAudit.Action.CREATED, GrantAudit.Action.REVOKED]


# ---------------------------------------------------------------------------
# Constraint: exactly one recipient (clean() + DB CheckConstraint)
# ---------------------------------------------------------------------------
def test_clean_requires_exactly_one_recipient():
    award = AwardTypeFactory.create()
    cycle = AwardCycleFactory.create()
    granter = UserFactory.create()
    # zero recipients
    with pytest.raises(ValidationError):
        AwardGrant(award_type=award, cycle=cycle, granted_by=granter).clean()
    # two recipients
    with pytest.raises(ValidationError):
        AwardGrant(
            award_type=award,
            cycle=cycle,
            granted_by=granter,
            recipient_member=UserFactory.create(),
            recipient_chapter=ChapterFactory.create(),
        ).clean()


def test_db_constraint_rejects_two_recipients():
    award = AwardTypeFactory.create()
    cycle = AwardCycleFactory.create()
    granter = UserFactory.create()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AwardGrant.objects.create(
                award_type=award,
                cycle=cycle,
                granted_by=granter,
                recipient_member=UserFactory.create(),
                recipient_region=RegionFactory.create(),
            )


def test_db_constraint_rejects_zero_recipients():
    award = AwardTypeFactory.create()
    cycle = AwardCycleFactory.create()
    granter = UserFactory.create()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AwardGrant.objects.create(award_type=award, cycle=cycle, granted_by=granter)


# ---------------------------------------------------------------------------
# Winner counting bridges AWI-2 enforcement to real grants
# ---------------------------------------------------------------------------
def test_count_active_winners_and_single_winner_enforcement():
    award = AwardTypeFactory.create(single_winner=True)
    cycle = AwardCycleFactory.create()
    granter = UserFactory.create()
    assert count_active_winners(award, cycle) == 0
    check_winner_allowed(award, count_active_winners(award, cycle))  # ok: no winners yet

    grant = grant_award(award, cycle, UserFactory.create(), granter)
    assert count_active_winners(award, cycle) == 1
    with pytest.raises(ValidationError):
        check_winner_allowed(award, count_active_winners(award, cycle))

    # revoking frees the single-winner slot
    revoke_grant(grant, granter)
    assert count_active_winners(award, cycle) == 0
    check_winner_allowed(award, count_active_winners(award, cycle))  # ok again


def test_count_active_winners_is_scoped_to_award_and_cycle():
    award = AwardTypeFactory.create()
    other_award = AwardTypeFactory.create()
    cycle = AwardCycleFactory.create()
    other_cycle = AwardCycleFactory.create()
    granter = UserFactory.create()
    grant_award(award, cycle, UserFactory.create(), granter)
    grant_award(other_award, cycle, UserFactory.create(), granter)
    grant_award(award, other_cycle, UserFactory.create(), granter)
    assert count_active_winners(award, cycle) == 1


# ---------------------------------------------------------------------------
# Outstanding Student Member award: granted by the forms-app OSM flow
# ---------------------------------------------------------------------------
def test_grant_osm_award_creates_grant_for_nominee():
    from thetatauCMT.awards.services import OSM_AWARD_NAME, grant_osm_award
    from thetatauCMT.forms.tests.factories import OSMFactory

    award = AwardTypeFactory.create(name=OSM_AWARD_NAME, level="active", grant_method="direct")
    osm = OSMFactory.create()
    grant = grant_osm_award(osm)
    assert grant is not None
    assert grant.award_type_id == award.pk
    assert grant.recipient_member_id == osm.nominate_id
    assert grant.recipient_kind == "member"
    assert grant.cycle.name == str(osm.year)
    assert grant.source == AwardGrant.Source.NOMINATION
    # granted_by defaults to the verifying officer
    assert grant.granted_by_id == osm.officer1_id


def test_grant_osm_award_is_idempotent():
    from thetatauCMT.awards.services import OSM_AWARD_NAME, grant_osm_award
    from thetatauCMT.forms.tests.factories import OSMFactory

    AwardTypeFactory.create(name=OSM_AWARD_NAME, level="active", grant_method="direct")
    osm = OSMFactory.create()
    first = grant_osm_award(osm)
    second = grant_osm_award(osm)
    assert first.pk == second.pk
    assert AwardGrant.objects.filter(recipient_member=osm.nominate).count() == 1


def test_grant_osm_award_missing_award_type_returns_none():
    from thetatauCMT.awards.services import grant_osm_award
    from thetatauCMT.forms.tests.factories import OSMFactory

    osm = OSMFactory.create()
    assert grant_osm_award(osm) is None
    assert not AwardGrant.objects.filter(recipient_member=osm.nominate).exists()
