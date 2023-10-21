from django.conf import settings
from django.utils.decorators import method_decorator
from django.forms.models import model_to_dict
from django.urls import reverse
from viewflow import flow
from viewflow.base import this, Flow
from viewflow.compat import _
from core.flows import (
    AutoAssignUpdateProcessView,
    NoAssignView,
    FilterableFlowViewSet,
    register_factory,
)
from .models import (
    MemberUpdate,
)
from forms.notifications import (
    EmailProcessUpdate,
)
from .forms import MemberUpdateForm


class AutoAssignUpdateProcessViewUser(AutoAssignUpdateProcessView):
    form_class = MemberUpdateForm


@register_factory(viewset_class=FilterableFlowViewSet)
class MemberUpdateFlow(Flow):
    """
    On create flow,
        if user exists send email to the original email giving 7 days to revert
            or click button to approve immediately

        If the user does not exist then need to match my CO
            CO will have option to match to user and update
                then continue on same process as original email giving X days to revert
            or create new user no original user create and end
            or deny and send email, could not verify, please call to rectify

        After X days, update the user with history, send confirmation, send to chapter CORSEC

    """

    process_class = MemberUpdate
    process_title = _("Member Update Process")
    process_description = _("This process is to update member info.")

    start = flow.StartFunction(
        this.create_flow, activation_class=flow.nodes.ManagedStartViewActivation
    ).Next(this.check_user)

    check_user = (
        flow.If(
            cond=lambda act: act.process.user is not None,
            task_title=_("Check if can auto update"),
        )
        .Then(this.email_delay)
        .Else(this.manual_match)
    )

    email_delay = flow.Handler(
        this.email_delay_func,
        task_title=_("Send email and then delay."),
    ).Next(this.delay)

    delay = flow.Function(
        this.placeholder,
        task_loader=lambda flow_task, task: task,
        task_title=_("Wait until update"),
    ).Next(this.check_approval)

    manual_match = (
        NoAssignView(
            AutoAssignUpdateProcessViewUser,
            task_title=_("Manual Member Update Match"),
            task_description=_("Manual Member Update Match"),
            task_result_summary=_("Outcome manual match: {{ process.outcome }}"),
        )
        .Permission("auth.central_office")
        .Next(this.check_manual_outcome)
    )

    check_manual_outcome = (
        flow.Switch()
        # An existing user was found, continue on same process as original email giving X days to revert
        .Case(this.email_delay, cond=lambda act: act.process.outcome == "matched")
        # Created a new user, run update function just to notify
        .Case(this.update, cond=lambda act: act.process.outcome == "created")
        # No user could be match, deny and notify
        .Case(this.deny_notify, cond=lambda act: act.process.outcome == "denied")
    )

    deny_notify = flow.Handler(
        this.deny_notify_func,
        task_title=_("Deny the Update and Notify"),
    ).Next(this.complete)

    check_approval = (
        flow.If(
            cond=lambda act: act.process.approved,
            task_title=_("Check if can update"),
        )
        .Then(this.update)
        .Else(this.complete)
    )

    update = flow.Handler(
        this.update_func,
        task_title=_("Apply the member update"),
    ).Next(this.complete)

    complete = flow.End(
        task_title=_("Complete"),
        task_result_summary=_("Member update process complete"),
    )

    @method_decorator(flow.flow_start_func)
    def create_flow(self, activation, user, updated: dict, **kwargs):
        if user is not None:
            activation.process.user = user
            activation.process.chapter = user.chapter
        else:
            if "school_name" in updated:
                school_name = updated.pop("school_name")
                activation.process.chapter = school_name
        for key, value in updated.items():
            setattr(activation.process, key, value)
        activation.process.save()
        activation.prepare()
        activation.done()
        return activation

    @method_decorator(flow.flow_func)
    def placeholder(self, activation, task):
        activation.prepare()
        activation.done()
        return activation

    def email_delay_func(self, activation):
        """
        Email the member that their info was changed, and they need to cancel if not approved
        :param activation:
        :return:
        """
        user = activation.process.user
        updated = MemberUpdateFlow.get_updated(activation.process, perform_update=False)
        host = settings.CURRENT_URL
        link = reverse("users:update_review", kwargs={"pk": activation.process.pk})
        link = host + link
        EmailProcessUpdate(
            activation,
            "Member Information Update",
            "Pending Approval",
            "Submitted",
            f"{user} has submitted an update to personal information in the CMT."
            + " Please review the changes. You can immediately approve or deny these changes by clicking on the link. <br>"
            + f"<a href='{link}'>Approve or deny changes here. ({link})</a><br>"
            + "<b>Otherwise these changes will go into affect in 7 days.</b>",
            list(updated.keys()),
        ).send()

    def deny_notify_func(self, activation):
        """
        Deny the update and notify the user
        """
        updated = MemberUpdateFlow.get_updated(activation.process, perform_update=False)
        activation.process.approved = False
        activation.process.save()

        class TempUser:
            """Because the user likely does not exist we need a temp user"""

            first_name = ""
            last_name = ""
            chapter = ""
            email = ""

            def __str__(self):
                return f"{self.first_name} {self.last_name}"

        temp_user = TempUser()
        temp_user.chapter = activation.process.chapter
        temp_user.email = activation.process.email
        temp_user.first_name = activation.process.first_name
        temp_user.last_name = activation.process.last_name
        extra_emails = {}
        if hasattr(activation.process, "email_school"):
            extra_emails = {activation.process.email_school}
        EmailProcessUpdate(
            activation,
            "DENIED Member Information Update",
            "Complete",
            "DENIED",
            f"{temp_user} submitted an update to personal information in the CMT."
            + " We were unable to find your member record to update the information. "
            "Please reach out to the central office at "
            "central.office@thetatau.org or 512.472.1904",
            list(updated.keys()),
            direct_user=temp_user,
            extra_emails=extra_emails,
        ).send()

    @classmethod
    def get_updated(cls, model, perform_update=True):
        updated = dict()
        user = model.user
        fields = [
            "badge_number",
            "title",
            "first_name",
            "middle_name",
            "last_name",
            "maiden_name",
            "preferred_pronouns",
            "preferred_name",
            "nickname",
            "suffix",
            "email",
            "email_school",
            "address",
            "birth_date",
            "phone_number",
            "graduation_year",
            "degree",
            "major",
            "major_other",
            "employer",
            "employer_position",
            "employer_address",
        ]
        for key in fields:
            value = getattr(model, key)
            if value:
                if user:
                    if getattr(user, key) != value:
                        updated[key] = value
                else:
                    updated[key] = value
        if updated and perform_update:
            updated["_change_reason"] = "Not Logged In Update Info"
            if user:
                for update, value in updated.items():
                    setattr(user, update, value)
                user.save()
            else:
                # There is no user to update
                pass
            updated.pop("_change_reason")
        return updated

    def update_func(self, activation):
        """
        Update the member's info
        """
        user = activation.process.user
        perform_update = True
        if activation.process.outcome == "created":
            # If the member was created then no need to update info
            perform_update = False
        updated = MemberUpdateFlow.get_updated(
            activation.process, perform_update=perform_update
        )

        EmailProcessUpdate(
            activation,
            "Approval Complete",
            "Complete",
            "Complete",
            f"{user} has submitted an update to personal information in the CMT."
            + " Please review the changes below. These changes have now been made, "
            "if you did not make these changes please notify the central office immediately at central.office@thetatau.org . ",
            list(updated.keys()),
            extra_emails=user.chapter.get_email_specific(
                roles=["corresponding secretary"]
            ),
        ).send()

    @classmethod
    def continue_process(cls, pk):
        # This will cause the delay step to process and then check_approval
        process = MemberUpdate.objects.get(pk=pk)
        cls.delay.run(process.get_task(cls.delay))
