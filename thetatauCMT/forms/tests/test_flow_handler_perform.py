"""Performing a Handler task again after an Undo (#1162).

viewflow lets a finished Handler task be undone (DONE -> NEW) while the task it
led to is still open. Its "Perform" action then ran the callback and 500'd in
``activate_next`` with ``TransitionNotAllowed``: the following task already
exists, so the ``all_leading_canceled`` condition fails.
"""

import pytest
from django.test import override_settings
from viewflow.activation import STATUS
from viewflow.models import Task

from thetatauCMT.forms.flows import PledgeProcessFlow


def _active_nodes(process):
    return [task.flow_task for task in process.active_tasks()]


def _process_at_invoice_payment(chapter):
    """A pledge process past "Send Invoice", waiting on "Invoice Payment"."""
    process = PledgeProcessFlow.start.run(chapter=chapter).process
    activation = Task.objects.get(process=process, flow_task=PledgeProcessFlow.invoice_chapter).activate()
    activation.prepare()
    activation.done()
    assert _active_nodes(process) == [PledgeProcessFlow.invoice_payment]
    return process


@pytest.mark.django_db
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_perform_after_undo_completes_without_duplicating_the_next_task(auto_login_user, admin_user, chapter):
    process = _process_at_invoice_payment(chapter)
    send_invoice = Task.objects.get(process=process, flow_task=PledgeProcessFlow.send_invoice)
    send_invoice.activate().undo()
    send_invoice.refresh_from_db()
    assert send_invoice.status == STATUS.NEW
    client, _ = auto_login_user(user=admin_user)

    response = client.post(
        f"/workflow/forms/pledgeprocess/{process.pk}/send_invoice/{send_invoice.pk}/perform/",
        {"run_action": "1"},
    )

    assert response.status_code == 302
    send_invoice.refresh_from_db()
    assert send_invoice.status == STATUS.DONE
    assert _active_nodes(process) == [PledgeProcessFlow.invoice_payment]
    assert Task.objects.filter(process=process, flow_task=PledgeProcessFlow.invoice_payment).count() == 1


@pytest.mark.django_db
def test_perform_after_undo_activates_next_once_the_following_task_is_canceled(chapter):
    process = _process_at_invoice_payment(chapter)
    payment = Task.objects.get(process=process, flow_task=PledgeProcessFlow.invoice_payment)
    payment.activate().cancel()
    send_invoice = Task.objects.get(process=process, flow_task=PledgeProcessFlow.send_invoice)
    send_invoice.activate().undo()
    send_invoice.refresh_from_db()

    send_invoice.activate().perform()

    statuses = sorted(
        Task.objects.filter(process=process, flow_task=PledgeProcessFlow.invoice_payment).values_list(
            "status", flat=True
        )
    )
    assert statuses == [STATUS.CANCELED, STATUS.NEW]


def test_every_flow_handler_can_be_performed_again():
    from viewflow import flow
    from viewflow.base import Flow

    import thetatauCMT.awards.flows  # noqa: F401
    import thetatauCMT.nominations.flows  # noqa: F401
    import thetatauCMT.users.flows  # noqa: F401
    from core.flows import RerunnableHandlerActivation

    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    plain = [
        f"{flow_class.__name__}.{node.name}"
        for flow_class in subclasses(Flow)
        if flow_class.__module__.startswith("thetatauCMT.")
        for node in flow_class._meta.nodes()
        if isinstance(node, flow.Handler) and not issubclass(node.activation_class, RerunnableHandlerActivation)
    ]
    assert plain == []
