"""VWI-5: Vetting node (reference/background check).

Pass -> interview; fail -> rejection (record retained); the vetting record is
persisted; the node is gated to the configured VettingReviewer.
"""

import pytest

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.users.tests.factories import UserFactory

from ._flow_helpers import active_task, advance_to, complete_view, done_task, start_nomination

pytestmark = pytest.mark.django_db


def _at_vetting(**kwargs):
    process = start_nomination(**kwargs)
    advance_to(process, "vetting")
    return process


def test_vetting_pass_routes_to_interview():
    process = _at_vetting()
    complete_view(process, NominationFlow.vetting, reference_check=True, vetting_passed=True)
    assert active_task(process, NominationFlow.interview) is not None
    assert active_task(process, NominationFlow.vetting) is None


def test_vetting_fail_routes_to_rejection_and_retains_record():
    process = _at_vetting()
    complete_view(process, NominationFlow.vetting, reference_check=True, vetting_passed=False)
    assert active_task(process, NominationFlow.interview) is None
    assert done_task(process, NominationFlow.rejected) is not None
    # Record retained; not_interested NOT set on a vetting failure.
    assert type(process).objects.filter(pk=process.pk).exists()
    process.refresh_from_db()
    assert process.not_interested is False


def test_vetting_record_fields_persist():
    process = _at_vetting()
    complete_view(
        process,
        NominationFlow.vetting,
        reference_check=True,
        vetting_notes="Checked two references; all positive.",
        vetting_passed=True,
    )
    process.refresh_from_db()
    assert process.reference_check is True
    assert process.vetting_notes == "Checked two references; all positive."
    assert process.vetting_passed is True


def test_vetting_gated_to_configured_reviewer():
    reviewer = UserFactory.create(username="vetter@example.com")
    Config.objects.create(key="VettingReviewer", value="vetter@example.com", description="v")
    process = _at_vetting()
    task = active_task(process, NominationFlow.vetting)
    assert task.owner == reviewer
    assert task.owner_permission is not None
    assert NominationFlow.vetting.can_execute(reviewer, task) is True
    assert NominationFlow.vetting.can_execute(UserFactory.create(), task) is False
