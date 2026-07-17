import logging

from viewflow import flow
from viewflow.base import Flow, this
from viewflow.compat import _

from core.flows import FilterableFlowViewSet, register_factory

from .models import AwardNominationProcess
from .services import get_award_approver, grant_from_nomination
from .views import AwardNominationCreateView, AwardNominationReviewView

logger = logging.getLogger(__name__)


def nomination_approved(activation):
    """Branch condition: the reviewer approved the nomination."""
    return activation.process.result == AwardNominationProcess.Result.APPROVED


@register_factory(viewset_class=FilterableFlowViewSet)
class AwardNominationFlow(Flow):
    """Award nomination + approval lifecycle.

    ::

        Start(entry) -> review -> [approved] approve -> End(approved)
                                -> [else]     reject  -> End(rejected)

    The role-scoped entry (AWI-6) starts the process; the ``review`` task is
    assigned to the config-driven approver (:func:`get_award_approver`, resolved
    per award level). Approval creates an ``AwardGrant(source=nomination)`` --
    the per-cycle winner rules are enforced in the review form -- and fires the
    ``award_granted`` signal; rejection closes the process with an optional
    reason. The nomination record is retained either way.
    """

    process_class = AwardNominationProcess
    process_title = _("Award Nomination")
    process_description = _("Nominate a recipient for an award and route it for review.")
    summary_template = "{{ flow_class.process_title }} - {{ process.recipient_display }}"

    start = flow.Start(
        AwardNominationCreateView,
        task_title=_("Submit Award Nomination"),
    ).Next(this.notify_submitted)

    notify_submitted = flow.Handler(
        this.notify_submitted_func,
        task_title=_("Notify Approver"),
    ).Next(this.review)

    review = (
        flow.View(
            AwardNominationReviewView,
            task_title=_("Review Award Nomination"),
            task_result_summary=_("Nomination {{ process.get_result_display|default:'pending' }}"),
        )
        .Assign(lambda act: get_award_approver(act.process.award_type))
        .Permission(auto_create=True)
        .Next(this.check_result)
    )

    check_result = flow.If(cond=nomination_approved, task_title=_("Approved?")).Then(this.approve).Else(this.reject)

    approve = flow.Handler(this.approve_func, task_title=_("Create Award Grant")).Next(this.approved)
    reject = flow.Handler(this.reject_func, task_title=_("Close Nomination")).Next(this.rejected)

    approved = flow.End(
        task_title=_("Approved"),
        task_result_summary=_("Grant created; record retained."),
    )
    rejected = flow.End(
        task_title=_("Rejected"),
        task_result_summary=_("Nomination rejected; record retained."),
    )

    def approve_func(self, activation):
        process = activation.process
        process.result = AwardNominationProcess.Result.APPROVED
        approver = process.reviewed_by or get_award_approver(process.award_type)
        grant = grant_from_nomination(process, approver)
        process.resulting_grant = grant
        process.save(update_fields=["result", "resulting_grant"])

    def reject_func(self, activation):
        process = activation.process
        process.result = AwardNominationProcess.Result.REJECTED
        process.save(update_fields=["result"])

    def notify_submitted_func(self, activation):
        from .notifications import AwardNominationSubmittedNotification

        process = activation.process
        approver = get_award_approver(process.award_type)
        try:
            notification = AwardNominationSubmittedNotification(process, approver)
            if notification.to_emails:
                notification.send()
        except Exception:
            logger.exception("Award nomination notification failed for process %s", process.pk)
