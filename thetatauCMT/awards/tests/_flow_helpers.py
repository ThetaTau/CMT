"""Shared helpers for driving AwardNominationFlow programmatically in tests.

Not a test module (name starts with ``_``) so pytest does not collect it.
"""

from viewflow.activation import STATUS
from viewflow.models import Task

from thetatauCMT.awards.flows import AwardNominationFlow
from thetatauCMT.awards.tests.factories import AwardCycleFactory, AwardTypeFactory
from thetatauCMT.users.tests.factories import UserFactory


def start_award_nomination(**kwargs):
    """Start an AwardNominationFlow; the process parks at the ``review`` node."""
    activation = AwardNominationFlow.start.activation_class()
    activation.initialize(AwardNominationFlow.start, None)
    process = activation.process
    process.award_type = kwargs.pop("award_type", None) or AwardTypeFactory(
        grant_method="nomination_workflow", level="member"
    )
    process.cycle = kwargs.pop("cycle", None) or AwardCycleFactory()
    if "recipient_member" in kwargs:
        process.recipient_member = kwargs.pop("recipient_member")
    else:
        process.recipient_member = UserFactory(status="active")
    process.nominator = kwargs.pop("nominator", None) or UserFactory()
    process.justification = kwargs.pop("justification", "Great work")
    for key, value in kwargs.items():
        setattr(process, key, value)
    activation.prepare()
    activation.done()
    if getattr(activation, "lock", None):
        activation.lock.__exit__(None, None, None)
    process.refresh_from_db()
    return process


def active_task(process, node):
    return Task.objects.filter(process=process, flow_task=node, status__in=[STATUS.NEW, STATUS.ASSIGNED]).first()


def done_task(process, node):
    return Task.objects.filter(process=process, flow_task=node, status=STATUS.DONE).first()


def complete_review(process, **updates):
    """Complete the waiting ``review`` task, applying decision fields first."""
    task = active_task(process, AwardNominationFlow.review)
    assert task is not None, "No active review task"
    for key, value in updates.items():
        setattr(process, key, value)
    if updates:
        process.save()
    activation = task.activate()
    if task.status == STATUS.NEW:
        activation.assign()
    activation.prepare()
    activation.done()
    process.refresh_from_db()
    return task
