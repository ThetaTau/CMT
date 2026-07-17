import pytest

from thetatauCMT.awards.flows import AwardNominationFlow
from thetatauCMT.awards.forms import WINNER_LIMIT_MSG, AwardNominationReviewForm
from thetatauCMT.awards.models import AwardGrant, AwardNominationProcess
from thetatauCMT.awards.services import get_award_approver, grant_from_nomination
from thetatauCMT.awards.signals import award_granted
from thetatauCMT.awards.tests._flow_helpers import active_task, complete_review, done_task, start_award_nomination
from thetatauCMT.awards.tests.factories import (
    AwardCycleFactory,
    AwardGrantFactory,
    AwardNominationProcessFactory,
    AwardTypeFactory,
)
from thetatauCMT.configs.models import Config
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Acceptance: nomination starts process (parks at review)
# ---------------------------------------------------------------------------
def test_nomination_starts_and_parks_at_review():
    process = start_award_nomination()
    assert process.pk is not None
    assert active_task(process, AwardNominationFlow.review) is not None


# ---------------------------------------------------------------------------
# Acceptance: approver resolved from config
# ---------------------------------------------------------------------------
def test_approver_resolved_from_config():
    approver = UserFactory(username="award.approver@example.com")
    Config.objects.create(key="AwardApprover", value="award.approver@example.com", description="Award approver")
    assert get_award_approver(AwardTypeFactory(level="national")) == approver


def test_approver_level_specific_config_wins():
    UserFactory(username="base@example.com")
    national = UserFactory(username="national@example.com")
    Config.objects.create(key="AwardApprover", value="base@example.com", description="base")
    Config.objects.create(key="AwardApprover:national", value="national@example.com", description="national")
    assert get_award_approver(AwardTypeFactory(level="national")) == national


def test_approver_resolves_national_officer_role():
    holder = UserFactory(current_roles=["grand regent"])
    Config.objects.create(key="AwardApprover", value="grand regent", description="role")
    assert get_award_approver(AwardTypeFactory(level="national")) == holder


# ---------------------------------------------------------------------------
# Acceptance: approve creates grant (source=nomination) + fires notifications
# ---------------------------------------------------------------------------
def test_approve_creates_grant_and_fires_signal():
    received = []

    def receiver(sender, grant, actor, **kwargs):
        received.append((grant, actor))

    award_granted.connect(receiver)
    try:
        award = AwardTypeFactory(grant_method="nomination_workflow", level="member")
        cycle = AwardCycleFactory()
        member = UserFactory(status="active")
        approver = UserFactory()
        process = start_award_nomination(award_type=award, cycle=cycle, recipient_member=member)
        complete_review(process, result="approved", reviewed_by=approver)
    finally:
        award_granted.disconnect(receiver)

    process.refresh_from_db()
    assert process.result == AwardNominationProcess.Result.APPROVED
    grant = process.resulting_grant
    assert grant is not None
    assert grant.source == AwardGrant.Source.NOMINATION
    assert grant.recipient == member
    assert grant.granted_by == approver
    assert received == [(grant, approver)]
    assert done_task(process, AwardNominationFlow.approved) is not None


# ---------------------------------------------------------------------------
# Acceptance: reject retains record with reason (no grant)
# ---------------------------------------------------------------------------
def test_reject_retains_record_with_reason():
    process = start_award_nomination()
    approver = UserFactory()
    complete_review(process, result="rejected", reject_reason="Not this cycle", reviewed_by=approver)
    process.refresh_from_db()
    assert process.result == AwardNominationProcess.Result.REJECTED
    assert process.reject_reason == "Not this cycle"
    assert process.resulting_grant is None
    assert process.reviewed_by == approver
    assert AwardNominationProcess.objects.filter(pk=process.pk).exists()
    assert not AwardGrant.objects.filter(recipient_member=process.recipient_member).exists()


# ---------------------------------------------------------------------------
# Acceptance: winner-count rules enforced at approval (review form)
# ---------------------------------------------------------------------------
def test_winner_rules_enforced_at_approval():
    award = AwardTypeFactory(grant_method="nomination_workflow", level="member", single_winner=True)
    cycle = AwardCycleFactory()
    AwardGrantFactory(award_type=award, cycle=cycle)  # single-winner slot already filled
    process = AwardNominationProcessFactory(award_type=award, cycle=cycle)
    form = AwardNominationReviewForm(data={"result": "approved"}, instance=process)
    assert not form.is_valid()
    assert WINNER_LIMIT_MSG in str(form.errors)


def test_review_form_approves_when_slot_available():
    award = AwardTypeFactory(grant_method="nomination_workflow", level="member", single_winner=True)
    process = AwardNominationProcessFactory(award_type=award, cycle=AwardCycleFactory())
    form = AwardNominationReviewForm(data={"result": "approved"}, instance=process)
    assert form.is_valid(), form.errors


def test_review_form_reject_always_valid():
    process = AwardNominationProcessFactory()
    form = AwardNominationReviewForm(data={"result": "rejected", "reject_reason": "no"}, instance=process)
    assert form.is_valid(), form.errors


def test_review_form_requires_a_decision():
    process = AwardNominationProcessFactory()
    form = AwardNominationReviewForm(data={"result": ""}, instance=process)
    assert not form.is_valid()


# ---------------------------------------------------------------------------
# grant_from_nomination service
# ---------------------------------------------------------------------------
def test_grant_from_nomination_creates_nomination_grant():
    process = AwardNominationProcessFactory()
    approver = UserFactory()
    grant = grant_from_nomination(process, approver)
    assert grant.source == AwardGrant.Source.NOMINATION
    assert grant.granted_by == approver
    assert grant.recipient == process.recipient_member
    assert grant.audit_entries.count() == 1
