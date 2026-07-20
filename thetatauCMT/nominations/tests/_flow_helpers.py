"""Shared helpers for driving NominationFlow programmatically in tests.

Not a test module (name starts with ``_``) so pytest does not collect it.
"""

from viewflow.activation import STATUS
from viewflow.models import Task

from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.users.tests.factories import UserFactory


def start_nomination(**kwargs):
    """Start a NominationFlow (runs send_consent_request) waiting at nominee_consent."""
    activation = NominationFlow.start.activation_class()
    activation.initialize(NominationFlow.start, None)
    process = activation.process
    process.nominator = kwargs.pop("nominator", None) or UserFactory.create()
    process.nominee = kwargs.pop("nominee", None) if "nominee" in kwargs else UserFactory.create()
    process.nominee_name = kwargs.pop("nominee_name", "")
    process.nominee_email = kwargs.pop("nominee_email", "")
    process.reason = kwargs.pop("reason", "Would be great")
    process.recommended_positions = kwargs.pop("recommended_positions", ["grand regent"])
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


def complete_view(process, node, **updates):
    """Complete a waiting View task, applying decision-field updates first."""
    task = active_task(process, node)
    assert task is not None, f"No active task at {node.name}"
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


_STEP_UPDATES = {
    "nominee_consent": {"consent_status": "interested"},
    "vetting": {"reference_check": True, "vetting_passed": True},
    "interview": {"interview_conducted": True, "interview_passed": True},
    "training": {"training_cmt_complete": True, "training_vector_complete": True, "training_completed": True},
    "confirmation": {"confirmed": True},
    "appointment": {},
}
_STEP_ORDER = ["nominee_consent", "vetting", "interview", "training", "confirmation", "appointment"]


def advance_to(process, target_name):
    """Complete happy-path View nodes until ``target_name`` is the active task."""
    for name in _STEP_ORDER:
        if name == target_name:
            return
        node = getattr(NominationFlow, name)
        if active_task(process, node) is not None:
            complete_view(process, node, **_STEP_UPDATES[name])


def email_text(email):
    parts = [email.subject, email.body or ""]
    parts += [content for content, _mime in getattr(email, "alternatives", [])]
    return "\n".join(parts)
