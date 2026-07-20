"""VWI-6: Interview node.

Continue -> training; stop -> rejection; interview date/notes persist; the node
is gated to the configured Interviewer.
"""

import datetime

import pytest

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.users.tests.factories import UserFactory

from ._flow_helpers import active_task, advance_to, complete_view, done_task, start_nomination

pytestmark = pytest.mark.django_db


def _at_interview(**kwargs):
    process = start_nomination(**kwargs)
    advance_to(process, "interview")
    return process


def test_interview_continue_routes_to_training():
    process = _at_interview()
    complete_view(
        process,
        NominationFlow.interview,
        interview_conducted=True,
        interview_passed=True,
    )
    assert active_task(process, NominationFlow.training) is not None
    assert active_task(process, NominationFlow.interview) is None


def test_interview_stop_routes_to_rejection():
    process = _at_interview()
    complete_view(process, NominationFlow.interview, interview_conducted=True, interview_passed=False)
    assert active_task(process, NominationFlow.training) is None
    assert done_task(process, NominationFlow.rejected) is not None
    process.refresh_from_db()
    assert process.not_interested is False


def test_interview_date_and_notes_persist():
    process = _at_interview()
    complete_view(
        process,
        NominationFlow.interview,
        interview_conducted=True,
        interview_date=datetime.date(2026, 3, 15),
        interview_notes="Strong candidate; enthusiastic.",
        interview_passed=True,
    )
    process.refresh_from_db()
    assert process.interview_conducted is True
    assert process.interview_date == datetime.date(2026, 3, 15)
    assert process.interview_notes == "Strong candidate; enthusiastic."


def test_interview_gated_to_configured_interviewer():
    interviewer = UserFactory.create(username="interviewer@example.com")
    Config.objects.create(key="Interviewer", value="interviewer@example.com", description="i")
    process = _at_interview()
    task = active_task(process, NominationFlow.interview)
    assert task.owner == interviewer
    assert task.owner_permission is not None
    assert NominationFlow.interview.can_execute(interviewer, task) is True
    assert NominationFlow.interview.can_execute(UserFactory.create(), task) is False
