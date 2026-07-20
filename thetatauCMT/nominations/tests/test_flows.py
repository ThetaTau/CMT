"""Flow-level tests for NominationFlow (VWI-1).

The flow is driven programmatically at the viewflow activation level (the same
lifecycle the HTTP views use: assign -> prepare -> done) so node-to-node
transitions and branch routing can be verified without HTTP / templates /
permissions machinery.
"""

import types

import pytest
from viewflow.activation import STATUS
from viewflow.models import Task

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations import flows
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Programmatic flow driver helpers
# ---------------------------------------------------------------------------
def start_nomination(**process_kwargs):
    """Start a NominationFlow (mimics the Start view) and return the process."""
    activation = NominationFlow.start.activation_class()
    activation.initialize(NominationFlow.start, None)
    process = activation.process
    for key, value in process_kwargs.items():
        setattr(process, key, value)
    activation.prepare()
    activation.done()
    # Release the process lock the start activation acquired (the HTTP path's
    # flow_start_view decorator normally does this).
    if getattr(activation, "lock", None):
        activation.lock.__exit__(None, None, None)
    return process


def active_task(process, flow_node):
    """The waiting (NEW/ASSIGNED) task at ``flow_node``, or None."""
    return Task.objects.filter(
        process=process,
        flow_task=flow_node,
        status__in=[STATUS.NEW, STATUS.ASSIGNED],
    ).first()


def done_task(process, flow_node):
    return Task.objects.filter(process=process, flow_task=flow_node, status=STATUS.DONE).first()


def complete_view(process, flow_node, **field_updates):
    """Complete a waiting View task, applying any decision-field updates first."""
    task = active_task(process, flow_node)
    assert task is not None, f"No active task at {flow_node.name}"
    if field_updates:
        for key, value in field_updates.items():
            setattr(process, key, value)
        process.save()
    activation = task.activate()
    if task.status == STATUS.NEW:
        activation.assign()
    activation.prepare()
    activation.done()
    return task


def _nominees():
    return {"nominator": UserFactory.create(), "nominee": UserFactory.create(), "reason": "Great fit"}


# ---------------------------------------------------------------------------
# Structural sanity
# ---------------------------------------------------------------------------
def test_flow_exposes_process_class_and_start():
    assert NominationFlow.process_class.__name__ == "Nomination"
    assert hasattr(NominationFlow, "start")
    # Every referenced node exists on the flow.
    for name in [
        "nominee_consent",
        "vetting",
        "interview",
        "training",
        "confirmation",
        "appointment",
        "appointed",
        "closed",
        "rejected",
        "denied",
        "follow_up_wait",
    ]:
        assert hasattr(NominationFlow, name), name


# ---------------------------------------------------------------------------
# Acceptance: branch nodes route correctly with stubbed decisions
# ---------------------------------------------------------------------------
def _stub(**process_fields):
    return types.SimpleNamespace(process=types.SimpleNamespace(**process_fields))


def test_branch_condition_functions_with_stubbed_decisions():
    interested = _stub(consent_status="interested")
    declined = _stub(consent_status="not_interested")
    later = _stub(consent_status="follow_up_later")
    assert flows.nominee_is_interested(interested) is True
    assert flows.nominee_is_not_interested(interested) is False
    assert flows.nominee_is_not_interested(declined) is True
    assert flows.nominee_wants_follow_up(later) is True

    assert flows.vetting_passed(_stub(vetting_passed=True)) is True
    assert flows.vetting_passed(_stub(vetting_passed=False)) is False
    assert flows.vetting_passed(_stub(vetting_passed=None)) is False
    assert flows.interview_passed(_stub(interview_passed=True)) is True
    assert flows.confirmation_approved(_stub(confirmed=True)) is True
    assert flows.confirmation_approved(_stub(confirmed=False)) is False


# ---------------------------------------------------------------------------
# Acceptance: happy-path transitions node-to-node
# ---------------------------------------------------------------------------
def test_happy_path_transitions_node_to_node():
    process = start_nomination(**_nominees())

    # Start -> nominee_consent (waiting View).
    assert active_task(process, NominationFlow.nominee_consent) is not None

    # interested -> Switch routes to vetting.
    complete_view(process, NominationFlow.nominee_consent, consent_status="interested")
    assert active_task(process, NominationFlow.nominee_consent) is None
    assert active_task(process, NominationFlow.vetting) is not None

    # vetting pass -> interview.
    complete_view(process, NominationFlow.vetting, vetting_passed=True)
    assert active_task(process, NominationFlow.interview) is not None

    # interview pass -> training.
    complete_view(process, NominationFlow.interview, interview_passed=True)
    assert active_task(process, NominationFlow.training) is not None

    # training -> confirmation.
    complete_view(process, NominationFlow.training, training_completed=True)
    assert active_task(process, NominationFlow.confirmation) is not None

    # confirm -> appointment.
    complete_view(process, NominationFlow.confirmation, confirmed=True)
    assert active_task(process, NominationFlow.appointment) is not None

    # appointment -> apply_appointment Handler (auto) -> End(appointed).
    complete_view(process, NominationFlow.appointment)
    process.refresh_from_db()
    assert process.appointed is True
    assert process.finished is not None
    assert done_task(process, NominationFlow.appointed) is not None


# ---------------------------------------------------------------------------
# Acceptance: branch nodes route correctly (driven through the flow)
# ---------------------------------------------------------------------------
def test_not_interested_routes_to_closed_and_retains_record():
    process = start_nomination(**_nominees())
    complete_view(process, NominationFlow.nominee_consent, consent_status="not_interested")
    assert active_task(process, NominationFlow.vetting) is None
    assert done_task(process, NominationFlow.closed) is not None
    process.refresh_from_db()
    assert process.finished is not None
    # Record is retained (not deleted).
    assert type(process).objects.filter(pk=process.pk).exists()


def test_follow_up_later_parks_awaiting_follow_up():
    process = start_nomination(**_nominees())
    complete_view(process, NominationFlow.nominee_consent, consent_status="follow_up_later")
    assert active_task(process, NominationFlow.vetting) is None
    # Parked at the follow_up_wait Function node (not ended).
    assert active_task(process, NominationFlow.follow_up_wait) is not None
    process.refresh_from_db()
    assert process.finished is None


def test_vetting_fail_routes_to_rejection():
    process = start_nomination(**_nominees())
    complete_view(process, NominationFlow.nominee_consent, consent_status="interested")
    complete_view(process, NominationFlow.vetting, vetting_passed=False)
    assert active_task(process, NominationFlow.interview) is None
    assert done_task(process, NominationFlow.rejected) is not None


def test_interview_fail_routes_to_rejection():
    process = start_nomination(**_nominees())
    complete_view(process, NominationFlow.nominee_consent, consent_status="interested")
    complete_view(process, NominationFlow.vetting, vetting_passed=True)
    complete_view(process, NominationFlow.interview, interview_passed=False)
    assert active_task(process, NominationFlow.training) is None
    assert done_task(process, NominationFlow.rejected) is not None


def test_confirmation_deny_routes_to_denial():
    process = start_nomination(**_nominees())
    complete_view(process, NominationFlow.nominee_consent, consent_status="interested")
    complete_view(process, NominationFlow.vetting, vetting_passed=True)
    complete_view(process, NominationFlow.interview, interview_passed=True)
    complete_view(process, NominationFlow.training, training_completed=True)
    complete_view(process, NominationFlow.confirmation, confirmed=False)
    assert active_task(process, NominationFlow.appointment) is None
    # Deny routes to the Central Office denial node (VWI-10), which then Ends.
    assert active_task(process, NominationFlow.denial_central_office) is not None


# ---------------------------------------------------------------------------
# Acceptance: node owners resolve from config (through the running flow)
# ---------------------------------------------------------------------------
def test_consent_task_assigned_to_nominee():
    nominee = UserFactory.create()
    process = start_nomination(nominator=UserFactory.create(), nominee=nominee, reason="x")
    consent_task = active_task(process, NominationFlow.nominee_consent)
    assert consent_task is not None
    assert consent_task.owner == nominee


def test_vetting_task_owner_resolves_from_config():
    reviewer = UserFactory.create(username="vetter@example.com")
    Config.objects.create(key="VettingReviewer", value="vetter@example.com", description="v")
    process = start_nomination(**_nominees())
    complete_view(process, NominationFlow.nominee_consent, consent_status="interested")
    vetting_task = active_task(process, NominationFlow.vetting)
    assert vetting_task is not None
    assert vetting_task.owner == reviewer
