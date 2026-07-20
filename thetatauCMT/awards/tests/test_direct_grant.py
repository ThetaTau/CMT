import datetime

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.awards.models import AwardGrant
from thetatauCMT.awards.services import can_grant_awards, direct_grant
from thetatauCMT.awards.signals import award_granted
from thetatauCMT.awards.tests._helpers import sign_rmp as _sign_rmp
from thetatauCMT.awards.tests.factories import AwardCycleFactory, AwardTypeFactory, EligibilityRuleFactory
from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

_NAMES = list(GREEK_ABR.values())


def _natoff():
    return UserFactory(is_superuser=True)  # user_is_national_officer -> unrestricted scope


# ---------------------------------------------------------------------------
# Acceptance: direct grant creates active grant
# ---------------------------------------------------------------------------
def test_direct_grant_creates_active_grant():
    award = AwardTypeFactory(grant_method="direct", level="member")
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    grant = direct_grant(award, cycle, member, _natoff(), reason="Great work")
    assert grant.pk is not None
    assert grant.status == AwardGrant.Status.ACTIVE
    assert grant.source == AwardGrant.Source.DIRECT
    assert grant.recipient == member
    assert grant.reason == "Great work"


def test_direct_grant_rejects_non_direct_award():
    award = AwardTypeFactory(grant_method="nomination_workflow", level="member")
    with pytest.raises(ValidationError):
        direct_grant(award, AwardCycleFactory(), UserFactory(status="active"), _natoff())


# ---------------------------------------------------------------------------
# Acceptance: eligibility enforced
# ---------------------------------------------------------------------------
def test_direct_grant_enforces_eligibility():
    award = AwardTypeFactory(grant_method="direct", level="member")
    EligibilityRuleFactory(award_type=award, rule_type="member_status", member_status="active")
    alumni = UserFactory(status="alumni")  # excluded by the active-only rule
    with pytest.raises(ValidationError):
        direct_grant(award, AwardCycleFactory(), alumni, _natoff())
    assert not AwardGrant.objects.filter(recipient_member=alumni).exists()


# ---------------------------------------------------------------------------
# Acceptance: single-winner blocked when already granted in cycle
# ---------------------------------------------------------------------------
def test_direct_grant_single_winner_blocked():
    award = AwardTypeFactory(grant_method="direct", level="member", single_winner=True)
    cycle = AwardCycleFactory()
    granter = _natoff()
    direct_grant(award, cycle, UserFactory(status="active"), granter)  # first winner ok
    with pytest.raises(ValidationError):
        direct_grant(award, cycle, UserFactory(status="active"), granter)


def test_single_winner_allowed_in_a_different_cycle():
    award = AwardTypeFactory(grant_method="direct", level="member", single_winner=True)
    granter = _natoff()
    direct_grant(award, AwardCycleFactory(), UserFactory(status="active"), granter)
    # a different cycle has its own winner slot
    grant = direct_grant(award, AwardCycleFactory(), UserFactory(status="active"), granter)
    assert grant.status == AwardGrant.Status.ACTIVE


# ---------------------------------------------------------------------------
# Acceptance: backdating works
# ---------------------------------------------------------------------------
def test_direct_grant_backdating():
    award = AwardTypeFactory(grant_method="direct", level="member")
    backdate = datetime.date(2015, 5, 1)
    grant = direct_grant(award, AwardCycleFactory(), UserFactory(status="active"), _natoff(), effective_date=backdate)
    assert grant.effective_date == backdate
    assert grant.granted_at.date() == timezone.now().date()


# ---------------------------------------------------------------------------
# Acceptance: role scoping enforced
# ---------------------------------------------------------------------------
def test_direct_grant_role_scope_enforced():
    chapter_a = ChapterFactory(name=_NAMES[0])
    chapter_b = ChapterFactory(name=_NAMES[1])
    award = AwardTypeFactory(grant_method="direct", level="member")
    cycle = AwardCycleFactory()
    granter = UserFactory(chapter=chapter_a)  # chapter-scoped actor (not natoff / RD)
    member_other = UserFactory(chapter=chapter_b, status="active")
    with pytest.raises(ValidationError):
        direct_grant(award, cycle, member_other, granter)
    # ... but they may grant within their own chapter
    member_own = UserFactory(chapter=chapter_a, status="active")
    grant = direct_grant(award, cycle, member_own, granter)
    assert grant.recipient == member_own


# ---------------------------------------------------------------------------
# Signal fires (AWI-8 / AWI-9 extension point)
# ---------------------------------------------------------------------------
def test_direct_grant_fires_award_granted_signal():
    received = []

    def receiver(sender, grant, actor, **kwargs):
        received.append((grant, actor))

    award_granted.connect(receiver)
    try:
        award = AwardTypeFactory(grant_method="direct", level="member")
        granter = _natoff()
        grant = direct_grant(award, AwardCycleFactory(), UserFactory(status="active"), granter)
    finally:
        award_granted.disconnect(receiver)
    assert received == [(grant, granter)]


# ---------------------------------------------------------------------------
# can_grant_awards role matrix
# ---------------------------------------------------------------------------
def test_can_grant_awards_matrix():
    assert can_grant_awards(UserFactory(is_superuser=True)) is True
    assert can_grant_awards(UserFactory()) is False

    officer = UserFactory()
    officer.groups.add(Group.objects.get_or_create(name="officer")[0])
    assert can_grant_awards(officer) is True

    rd = UserFactory()
    RegionFactory().directors.add(rd)
    assert can_grant_awards(rd) is True


# ---------------------------------------------------------------------------
# View: access gating + happy path + error path
# ---------------------------------------------------------------------------
def _view_granter():
    # A natoff-GROUP user: unrestricted award scope and NOT a superuser (so the
    # superuser-2FA middleware does not intercept), with a current RMP signature.
    user = UserFactory()
    user.groups.add(Group.objects.get_or_create(name="natoff")[0])
    _sign_rmp(user)
    return user


def test_view_redirects_anonymous(client):
    resp = client.get(reverse("awards:direct_grant"))
    assert resp.status_code == 302


def test_view_blocks_non_officer(client):
    member = UserFactory()
    _sign_rmp(member)
    client.force_login(member)
    resp = client.get(reverse("awards:direct_grant"))
    assert resp.status_code == 302
    assert resp.url == reverse("home")


def test_view_officer_get_ok(client):
    client.force_login(_view_granter())
    resp = client.get(reverse("awards:direct_grant"))
    assert resp.status_code == 200


def test_view_post_creates_grant(client):
    award = AwardTypeFactory(grant_method="direct", level="member")
    cycle = AwardCycleFactory()
    member = UserFactory(status="active")
    client.force_login(_view_granter())
    resp = client.post(
        reverse("awards:direct_grant"),
        {"award_type": award.pk, "cycle": cycle.pk, "recipient_member": member.pk, "reason": "Great"},
    )
    assert resp.status_code == 302
    assert AwardGrant.objects.filter(award_type=award, recipient_member=member, status="active").exists()


def test_view_post_ineligible_reshows_form_with_error(client):
    award = AwardTypeFactory(grant_method="direct", level="member")
    EligibilityRuleFactory(award_type=award, rule_type="member_status", member_status="active")
    cycle = AwardCycleFactory()
    alumni = UserFactory(status="alumni")
    client.force_login(_view_granter())
    resp = client.post(
        reverse("awards:direct_grant"),
        {"award_type": award.pk, "cycle": cycle.pk, "recipient_member": alumni.pk},
    )
    assert resp.status_code == 200
    assert not AwardGrant.objects.filter(recipient_member=alumni).exists()
