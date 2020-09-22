import datetime
from django.conf import settings
from django.core.files.base import ContentFile
from django.urls import reverse
from django.utils.decorators import method_decorator
from viewflow import flow, frontend
from viewflow.base import this, Flow
from viewflow.compat import _
from viewflow.flow import views as flow_views
from easy_pdf.rendering import render_to_pdf
from core.models import forever
from core.flows import AutoAssignUpdateProcessView, NoAssignView
from .models import (
    PrematureAlumnus,
    InitiationProcess,
    Convention,
    PledgeProcess,
    OSM,
    DisciplinaryProcess,
    ResignationProcess,
)
from .views import (
    PrematureAlumnusCreateView,
    ConventionCreateView,
    ConventionSignView,
    FilterableFlowViewSet,
    OSMCreateView,
    OSMVerifyView,
    DisciplinaryCreateView,
    DisciplinaryForm2View,
    get_signature,
    ResignationCreateView,
    ResignationSignView,
)
from .forms import DisciplinaryForm1, DisciplinaryForm2
from .notifications import (
    EmailProcessUpdate,
    EmailConventionUpdate,
    EmailOSMUpdate,
    CentralOfficeGenericEmail,
)
from users.models import User, UserStatusChange


@frontend.register
class PrematureAlumnusFlow(Flow):
    process_class = PrematureAlumnus
    process_title = _("Premature Alumnus Process")
    process_description = _("This process is for premature alumnus processing.")

    start = (
        flow.Start(
            PrematureAlumnusCreateView, task_title=_("Request Premature Alumnus")
        )
        .Permission(auto_create=True)
        .Next(this.pending_status)
    )

    pending_status = flow.Handler(
        this.set_status_email, task_title=_("Set pending status, send email."),
    ).Next(this.exec_approve)

    exec_approve = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["approved_exec", "exec_comments",],
            task_title=_("Executive Director Review"),
            task_description=_("Pre Alumn Executive Director Review"),
            task_result_summary=_(
                "Messsage was {{ process.approved_exec|yesno:'Approved,Rejected' }}"
            ),
        )
        .Assign(lambda act: User.objects.get(username="Jim.Gaffney@thetatau.org"))
        .Next(this.check_approve)
    )

    check_approve = (
        flow.If(
            cond=lambda act: act.process.approved_exec,
            task_title=_("Premature Alumnus Approvement check"),
        )
        .Then(this.alumni_status)
        .Else(this.pending_undo)
    )

    alumni_status = flow.Handler(
        this.set_alumni_status, task_title=_("Set status alumni"),
    ).Next(this.send)

    pending_undo = flow.Handler(
        this.pending_undo_func, task_title=_("Set status active"),
    ).Next(this.send)

    send = flow.Handler(
        this.send_approval_complete, task_title=_("Send request complete message"),
    ).Next(this.complete)

    complete = flow.End(
        task_title=_("Complete"),
        task_result_summary=_(
            "Request was {{ process.approved_exec|yesno:'Approved,Rejected' }}"
        ),
    )

    def set_status_email(self, activation):
        """
        Need to set the pending status
        Email the user the form was received
        :param activation:
        :return:
        """
        user = activation.process.user
        created = activation.process.created
        active = user.status.order_by("-end").filter(status="active").first()
        if not active:
            print(f"There was no active status for user {user}")
            UserStatusChange(
                user=user,
                status="active",
                created=created,
                start=created - datetime.timedelta(days=365),
                end=created,
            ).save()
        else:
            active.end = created
            active.created = created
            active.save()
        alumnipends = user.status.filter(status="alumnipend")
        if alumnipends:
            alumnipend = alumnipends[0]
            alumnipend.start = created
            alumnipend.end = forever()
            alumnipend.created = created
            alumnipend.save()
            for alumnipend in alumnipends[1:]:
                alumnipend.delete()
        else:
            UserStatusChange(
                user=user,
                created=created,
                status="alumnipend",
                start=created,
                end=forever(),
            ).save()
        EmailProcessUpdate(
            activation,
            "Premature Alumnus Request",
            "Executive Director Review",
            "Submitted",
            "Your chapter has submitted a premature alumnus form on your behalf."
            + " Once the Central Office processes "
            + "the form, you will receive an email confirming your change in status.",
            [
                "good_standing",
                "financial",
                "semesters",
                "lifestyle",
                "consideration",
                "prealumn_type",
                "vote",
            ],
        ).send()

    def pending_undo_func(self, activation):
        user = activation.process.user
        alumnipends = user.status.filter(status="alumnipend")
        if alumnipends:
            for alumnipend in alumnipends:
                alumnipend.delete()
        active = user.status.order_by("-end").filter(status="active").first()
        active.end = forever()
        active.save()

    def set_alumni_status(self, activation):
        user = activation.process.user
        alumnipend = user.status.order_by("-end").filter(status="alumnipend").first()
        created = activation.task.created
        if not alumnipend:
            print(f"There was no alumnipend status for user {user}")
            UserStatusChange(
                user=user,
                status="alumnipend",
                created=created,
                start=created - datetime.timedelta(days=365),
                end=created,
            ).save()
        else:
            alumnipend.end = created
            alumnipend.save()
        alumnis = user.status.filter(status="alumni")
        if alumnis:
            alumni = alumnis[0]
            alumni.start = created
            alumni.end = forever()
            alumni.created = created
            alumni.save()
            for alumni in alumnis[1:]:
                alumni.delete()
        else:
            UserStatusChange(
                user=user,
                created=created,
                status="alumni",
                start=created,
                end=forever(),
            ).save()

    def send_approval_complete(self, activation):
        if activation.process.approved_exec:
            state = "Approved"
        else:
            state = "Rejected"
        EmailProcessUpdate(
            activation,
            "Executive Director Review",
            "Complete",
            state,
            "",
            ["approved_exec", "exec_comments",],
        ).send()


def register_factory(viewset_class):
    def decorator(function):
        return frontend.register(function, viewset_class=viewset_class)

    return decorator


@register_factory(viewset_class=FilterableFlowViewSet)
class InitiationProcessFlow(Flow):
    """
    Chapter submits initiation report
    CO receives a weekly batch of initiation reports (pref on Wednesday)
        that include individual csv files for each chapter with all of the info.
            These will be used for invoicing and eventual upload into Blackbaud
    CO invoices chapters based on those csv forms.
    CO goes into CMT and indicates which chapters have been invoiced.
    Invoice is paid by chapter.
    CO goes into CMT and indicates invoice paid.
    CMT provides (via email or download, whatever) csv files for jeweler and shingle company
    CO updates blackbaud using the CSV you previously sent and sends orders to badge/shingle company.
    CO goes into CMT to indicate that badge/shingle order has been placed
    """

    process_class = InitiationProcess
    process_title = _("Initiation Process")
    process_description = _("This process is for initiation form processing.")
    summary_template = "{{ flow_class.process_title }} - {{ process.chapter }}"

    start = flow.StartFunction(
        this.create_flow, activation_class=flow.nodes.ManagedStartViewActivation
    ).Next(this.invoice_chapter)
    start_manual = (
        flow.Start(flow_views.CreateProcessView, fields=["chapter",])
        .Permission(auto_create=True)
        .Next(this.invoice_chapter)
    )

    invoice_chapter = (
        NoAssignView(
            AutoAssignUpdateProcessView,
            fields=["invoice",],
            task_title=_("Invoice Chapter"),
            task_description=_("Send invoice to chapter"),
            task_result_summary=_("Invoice was sent to chapter"),
        )
        .Permission("auth.central_office")
        .Next(this.invoice_payment)
    )

    send_invoice = flow.Handler(
        this.send_invoice_func, task_title=_("Send Invoice"),
    ).Next(this.invoice_payment)

    invoice_payment = (
        NoAssignView(
            AutoAssignUpdateProcessView,
            task_title=_("Invoice Payment"),
            task_description=_("Invoice payment by chapter"),
            task_result_summary=_("Invoice paid by chapter"),
        )
        .Permission("auth.central_office")
        .Next(this.invoice_payment_email)
    )

    invoice_payment_email = flow.Handler(
        this.send_invoice_payment_email, task_title=_("Send Invoice Payment Email"),
    ).Next(this.order_complete)

    order_complete = (
        NoAssignView(
            AutoAssignUpdateProcessView,
            task_title=_("Order Complete"),
            task_description=_("Badge/shingle placing order"),
            task_result_summary=_("Badge/shingle order has been placed"),
        )
        .Permission("auth.central_office")
        .Next(this.send_order)
    )

    send_order = flow.Handler(this.send_order_func, task_title=_("Send Order"),).Next(
        this.complete
    )

    complete = flow.End(
        task_title=_("Complete"), task_result_summary=_("Initiation Process Complete")
    )

    @method_decorator(flow.flow_start_func)
    def create_flow(
        self,
        activation,
        initiations,
        ceremony="normal",
        request=None,
        created=None,
        **kwargs,
    ):
        activation.process.chapter = initiations[0].user.chapter
        activation.process.ceremony = ceremony
        activation.process.save()
        if request is not None:
            activation.prepare(None, user=request.user)
        else:
            activation.prepare()
        activation.done()
        if created is not None:
            activation.process.created = created
            activation.process.save()
        member_list = []
        for initiation in initiations:
            activation.process.initiations.add(initiation)
            member_list.append(initiation.user.name)
        member_list = ", ".join(member_list)
        EmailProcessUpdate(
            activation,
            "Initiation Report Submitted",
            "Central Office Processing & Invoice Generation",
            "Submitted",
            "Your chapter has submitted an initiation report."
            + " Once the Central Office processes the report, an invoice will be generated"
            + " and will be sent to your chapter on the last business day of this month.",
            [{"members": member_list},],
        ).send()
        return activation

    def send_invoice_func(self, activation):
        ...

    def send_invoice_payment_email(self, activation):
        member_list = activation.process.initiations.values_list(
            "user__email", flat=True
        )
        member_list = ", ".join(member_list)
        EmailProcessUpdate(
            activation,
            "Initiation Invoice Paid",
            "Central Office Badge/Shingle Order",
            "Payment Received",
            "Your chapter has paid an initiation invoice."
            + " Once the Central Office processes the payment, an order will be sent"
            + " to the jeweler/shingler.",
            [{"members": member_list}, "invoice",],
        ).send()

    def send_order_func(self, activation):
        member_list = activation.process.initiations.values_list(
            "user__email", flat=True
        )
        member_list = ", ".join(member_list)
        EmailProcessUpdate(
            activation,
            "Badge/Shingles Order Submitted",
            "Initiation Process Complete",
            "Badges/Shingles Ordered",
            "A badges and shingles order has been sent to the vendor.",
            [{"members": member_list}, "invoice",],
        ).send()


@frontend.register
class ConventionFlow(Flow):
    process_class = Convention
    process_title = _("Convention Process")
    process_description = _(
        "This process is for delegeate and alternate for convention."
    )

    start = flow.Start(
        ConventionCreateView, task_title=_("Submit Convention Form")
    ).Next(this.email_signers)

    email_signers = flow.Handler(
        this.email_signers_func, task_title=_("Email Signers"),
    ).Next(this.assign_approval)

    assign_approval = (
        flow.Split()
        .Next(this.assign_del,)
        .Next(this.assign_alt,)
        .Next(this.assign_o1)
        .Next(this.assign_o2)
    )

    assign_del = (
        flow.View(ConventionSignView, task_title=_("Delegate Sign"))
        .Assign(lambda act: act.process.delegate)
        .Next(this.join_flow)
    )

    assign_alt = (
        flow.View(ConventionSignView, task_title=_("Alternate Sign"))
        .Assign(lambda act: act.process.alternate)
        .Next(this.join_flow)
    )

    assign_o1 = (
        flow.View(ConventionSignView, task_title=_("Officer1 Sign"))
        .Assign(lambda act: act.process.officer1)
        .Next(this.join_flow)
    )

    assign_o2 = (
        flow.View(ConventionSignView, task_title=_("Officer2 Sign"))
        .Assign(lambda act: act.process.officer2)
        .Next(this.join_flow)
    )

    join_flow = flow.Join().Next(this.end)

    end = flow.End()

    def email_signers_func(self, activation):
        """
        Send emails to the signers
        :param activation:
        :return:
        """
        for user_role in ["delegate", "alternate", "officer1", "officer2"]:
            user = getattr(activation.process, user_role)
            EmailConventionUpdate(
                activation, user, "Convention Credential Form Submitted",
            ).send()


@register_factory(viewset_class=FilterableFlowViewSet)
class PledgeProcessFlow(Flow):
    """
    Pledge submits pledge form
        Look for existing Pledge Process and join that one, if does not exist
        create a new one
    These emails are outside of process:
        CMT generates two emails to pledge
            General welcome email and information confirmation
            EverFi sign-up email
            CMT generates email to chapter scribe and treasurer indicating a new pledge has filled out the form
    CO marks pledges group as processed and invoice number
        CO generates invoice and sends to chapter
            CSV for upload into Blackbaud
            CSV that contains only pledge's name, email address and the date they filled out the form (this is what we attach to the invoice)
    Invoice is paid by chapter
    CO goes into CMT and indicates invoice paid
    """

    process_class = PledgeProcess
    process_title = _("Pledge Process")
    process_description = _("This process is for pledge form processing.")
    summary_template = "{{ flow_class.process_title }} - {{ process.chapter }}"

    start = flow.StartFunction(
        this.create_flow, activation_class=flow.nodes.ManagedStartViewActivation
    ).Next(this.invoice_chapter)

    invoice_chapter = (
        NoAssignView(
            AutoAssignUpdateProcessView,
            fields=["invoice",],
            task_title=_("Invoice Chapter"),
            task_description=_("Send invoice to chapter"),
            task_result_summary=_("Invoice was sent to chapter"),
        )
        .Permission("auth.central_office")
        .Next(this.send_invoice)
    )

    send_invoice = flow.Handler(
        this.send_invoice_func, task_title=_("Send Invoice"),
    ).Next(this.invoice_payment)

    invoice_payment = (
        NoAssignView(
            AutoAssignUpdateProcessView,
            task_title=_("Invoice Payment"),
            task_description=_("Invoice payment by chapter"),
            task_result_summary=_("Invoice paid by chapter"),
        )
        .Permission("auth.central_office")
        .Next(this.invoice_payment_email)
    )

    invoice_payment_email = flow.Handler(
        this.send_invoice_payment_email, task_title=_("Send Invoice Payment Email"),
    ).Next(this.sync_member_info)

    sync_member_info = flow.Handler(
        this.sync_member_info_function, task_title=_("Sync Member Info"),
    ).Next(this.complete)

    complete = flow.End(
        task_title=_("Complete"), task_result_summary=_("Pledge Process Complete")
    )

    @method_decorator(flow.flow_start_func)
    def create_flow(self, activation, chapter, request=None, created=None, **kwargs):
        activation.process.chapter = chapter
        activation.process.save()
        activation.prepare()
        activation.done()
        if created is not None:
            activation.process.created = created
            activation.process.save()
        return activation

    def send_invoice_func(self, activation):
        ...

    def send_invoice_payment_email(self, activation):
        member_list = activation.process.pledges.values_list("email_school", flat=True)
        member_list = ", ".join(member_list)
        EmailProcessUpdate(
            activation,
            "Pledge Invoice Paid",
            "Complete",
            "Payment Received",
            "Your chapter has paid a pledge invoice.",
            [{"members": member_list}, "invoice",],
            email_officers=True,
        ).send()

    def sync_member_info_function(self, activation):
        pledges = activation.process.pledges.all()
        for pledge in pledges:
            # Update the User database with the new members
            # currently this is done in the CRM
            print(pledge)


@frontend.register
class OSMFlow(Flow):
    """
    Chapter officer fills out form to nominate their chapter OSM for the national award.
    Questions on form:
        - Select chapter member from dropdown list (self-nomination is allowed)
        - Date decision was made [date]
        - How was the Chapter Outstanding Student Member chosen?
            What process was used to select them? [paragraph field]
    Form should then be sent to chapter VR and scribe to verify -
        simple "yes, this is correct," "no, this isn't correct."
    After verification, email should be sent to the nominated member with
        link to fill out the application.
    """

    process_class = OSM
    process_title = _("OSM Process")
    process_description = _("This process is for outstanding student member selection.")

    start = flow.Start(OSMCreateView, task_title=_("Submit OSM Form")).Next(
        this.email_signers
    )

    email_signers = flow.Handler(
        this.email_signers_func, task_title=_("Email Signers"),
    ).Next(this.assign_approval)

    assign_approval = flow.Split().Next(this.assign_o1).Next(this.assign_o2)

    assign_o1 = (
        flow.View(OSMVerifyView, task_title=_("Officer1 Sign"))
        .Assign(lambda act: act.process.officer1)
        .Next(this.join_flow)
    )

    assign_o2 = (
        flow.View(OSMVerifyView, task_title=_("Officer2 Sign"))
        .Assign(lambda act: act.process.officer2)
        .Next(this.join_flow)
    )

    join_flow = flow.Join().Next(this.email_nominate)

    email_nominate = flow.Handler(
        this.email_nomination, task_title=_("Email Nominate"),
    ).Next(this.end)

    end = flow.End()

    def email_signers_func(self, activation):
        """
        Send emails to the signers
        :param activation:
        :return:
        """
        for user_role in ["officer1", "officer2"]:
            user = getattr(activation.process, user_role)
            EmailOSMUpdate(
                activation,
                user,
                "OSM Form Submitted",
                nominate=activation.process.nominate,
            ).send()

    def email_nomination(self, activation):
        user = activation.process.nominate
        EmailOSMUpdate(
            activation, user, "Outstanding Student Member Nomination",
        ).send()


@register_factory(viewset_class=FilterableFlowViewSet)
class DisciplinaryProcessFlow(Flow):
    """
    Form 1 - Initial Report of Charges
        Copy of form result sent to all
    Form 2 - Trial Report
        Form automatically emailed to chapter regent on the day of the trial
            rescheduling the form should ‘snooze’ until the new date
        Copy of form result sent to all
    It should generate a workflow item for the ED to process the form,
    If rejected, form 2 should be reopened so that the chapter can edit it again.
    If accepted with no action, generate PDFs of the two forms and email to CO for filing, complete workflow.
    If accepted for processing of expulsion/suspension, a form letter should be generated
        and it should be emailed to all
    Form 3 -- Send to EC
        show up as a task 45 days after the email above is sent and be assigned to ED.
        It should include a download option for forms 1 & 2 as well as all of the attachments and the form-letter form 2.
            Once downloaded I should be able to click “sent to EC.”
    Form 4 -- Outcome of EC
        This form should be assigned to ED. Option will be “Outcome approved by EC” or “Outcome Rejected by EC”
    “Rejected” completes workflow.
    “Approved” should generate a form letter (I’ll email that to you separately) and email it to all.
    Workflow complete.
    """

    process_class = DisciplinaryProcess
    process_title = _("Disciplinary Process")
    process_description = _("This process is for chapter disciplinary process.")

    restart = flow.StartFunction(
        this.restart_flow, activation_class=flow.nodes.ManagedStartViewActivation
    ).Next(this.email_form1_rescheduled)

    email_form1_rescheduled = flow.Handler(
        this.email_all, task_title=_("Email Form 1 Rescheduled"),
    ).Next(this.delay)

    start = flow.Start(
        DisciplinaryCreateView, task_title=_("Submit Disciplinary Form")
    ).Next(this.email_form1)

    email_form1 = flow.Handler(
        this.email_all, task_title=_("Email Form 1 Result"),
    ).Next(this.delay)

    delay = flow.Function(
        this.placeholder,
        task_loader=lambda flow_task, task: task,
        task_title=_("Wait Until Trial"),
    ).Next(this.email_regent)

    email_regent = flow.Handler(
        this.email_regent_func, task_title=_("Email Regent Form 2"),
    ).Next(this.submit_form2)

    submit_form2 = (
        flow.View(DisciplinaryForm2View, task_title=_("Submit Form 2"))
        .Assign(
            lambda act: act.process.chapter.get_current_officers_council_specific()[0]
        )
        .Next(this.check_reschedule)
    )

    check_reschedule = (
        flow.If(
            cond=lambda act: act.process.why_take == "rescheduled",
            task_title=_("Reschedule check"),
        )
        .Then(this.reschedule)
        .Else(this.exec_approve)
    )

    reschedule = flow.Handler(
        this.reschedule_func, task_title=_("Reschedule Disciplinary Process"),
    ).Next(this.end_reschedule)

    end_reschedule = flow.End(
        task_title=_("Rescheduled Disciplinary Process"),
        task_result_summary=_("Disciplinary process rescheduled by the chapter"),
    )

    exec_approve = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["ed_process", "ed_notes"],
            task_title=_("Executive Director Review"),
            task_description=_("Disciplinary Executive Director Review"),
            task_result_summary=_("Message was {{ process.ed_process' }}"),
        )
        .Assign(lambda act: User.objects.get(username="Jim.Gaffney@thetatau.org"))
        .Next(this.check_approve)
    )

    check_approve = (
        flow.Switch()
        .Case(this.reject_fix, cond=lambda act: act.process.ed_process == "reject")
        .Case(this.accept_done, cond=lambda act: act.process.ed_process == "accept")
        .Default(this.email_outcome_letter)
    )

    reject_fix = flow.Handler(
        this.email_regent_func, task_title=_("Reject Chapter Fix"),
    ).Next(this.submit_form2)

    accept_done = flow.Handler(
        this.accept_done_func, task_title=_("Accept File Done"),
    ).Next(this.end)

    email_outcome_letter = flow.Handler(
        this.email_all, task_title=_("Email Outcome Letter"),
    ).Next(this.delay_ec)

    delay_ec = flow.Function(
        this.placeholder,
        task_loader=lambda flow_task, task: task,
        task_title=_("Wait for Review"),
    ).Next(this.send_ec)

    send_ec = (
        flow.View(
            flow_views.UpdateProcessView,
            task_title=_("Send to EC"),
            task_description=_("Send to EC for review"),
        )
        .Assign(lambda act: User.objects.get(username="Jim.Gaffney@thetatau.org"))
        .Next(this.ec_review)
    )

    ec_review = (
        flow.View(
            flow_views.UpdateProcessView,
            fields=["ec_approval", "ec_notes"],
            task_title=_("Executive Council Review"),
            task_description=_("Disciplinary Executive Council Review"),
            task_result_summary=_(
                "Process was {{ process.ec_approval|yesno:'Outcome approved by EC,Outcome Rejected by EC' }}"
            ),
        )
        .Assign(lambda act: User.objects.get(username="Jim.Gaffney@thetatau.org"))
        .Next(this.email_final)
    )

    email_final = flow.Handler(
        this.email_all, task_title=_("Email Final Result"),
    ).Next(this.end)

    end = flow.End(task_title=_("Disciplinary Process Complete"),)

    @method_decorator(flow.flow_start_func)
    def restart_flow(self, activation, old_activation, **kwargs):
        fields = DisciplinaryForm1._meta.fields[:]
        process = old_activation.process
        for field in fields:
            value = getattr(process, field)
            setattr(activation.process, field, value)
        activation.process.trial_date = process.rescheduled_date
        activation.process.chapter = process.chapter
        activation.process.save()
        activation.prepare()
        activation.done()
        return activation

    @method_decorator(flow.flow_func)
    def placeholder(self, activation, task):
        activation.prepare()
        activation.done()
        return activation

    def email_all(self, activation):
        """
        A copy of forms should be sent to all chapter officers, central.office,
            the RD and the ED and riskchair@thetatau.org and accused
        """
        task_title = activation.flow_task.task_title
        complete_step, next_step, state, message, fields, attachments = (
            "",
            "",
            "",
            "",
            [],
            [],
        )
        if "Email Form 1" in task_title:
            next_step = "Wait for Trial"
            if "Rescheduled" in task_title:
                complete_step = "Disciplinary Process Rescheduled"
                state = "Rescheduled"
                message = (
                    "This is a notification that the Central Office has been "
                    "informed that your disciplinary trial has been rescheduled. "
                    "Please contact the Central Office if you have concerns or "
                    "questions."
                )
            else:
                complete_step = "Disciplinary Process Started"
                state = "Form 1 Submitted"
                message = (
                    "This is a notification that your chapter has"
                    " reported a disciplinary proceeding against you."
                    " Please see below for the details of the charges and "
                    "proceedings. If you have questions, please email or call "
                    "the Central Office at central.office@thetatau.org // "
                    "512-472-1904."
                )
            fields = DisciplinaryForm1._meta.fields[:]
            fields.remove("charging_letter")
            attachments = ["charging_letter"]
        elif "Email Outcome Letter" in task_title:
            image_string = get_signature()
            content = render_to_pdf(
                "forms/disciplinary_outcome_letter.html",
                context={"object": activation.process, "signature": image_string},
            )
            # with open("tests/outcome_letter.pdf", "wb") as f:
            #     f.write(content)
            activation.process.outcome_letter.save(
                "outcome_letter.pdf", ContentFile(content), save=True,
            )
            complete_step = "Executive Director Review"
            next_step = "Wait for Executive Council Review"
            state = "Pending Executive Council Review"
            if activation.process.why_take == "waived":
                message = (
                    "This if a notification that the Central Office has "
                    "received word from your Chapter that you waived your right "
                    "to a trial in the pending disciplinary matter against you. "
                    "As such, please see the attached document for a letter outlining "
                    "the Chapter’s decision and what will happen next. "
                    "If you have questions, please email or call the Central "
                    "Office at central.office@thetatau.org // 512-472-1904."
                )
            else:
                message = (
                    "This is a notification that a trial was held by your chapter "
                    "pursuant to the charges that were filed on "
                    f"{activation.process.trial_date} "
                    "Please see the attached letter for details on the outcome of "
                    "that trial and what will happen next."
                )
            attachments = ["outcome_letter"]
            fields = ["ed_process", "ed_notes"]
            today = datetime.datetime.today()
            activation.process.send_ec_date = today + datetime.timedelta(days=45)
            activation.process.save()
        elif "Email Final Result" in task_title:
            attachments = []
            if activation.process.ec_approval:
                # EC approved the expulsion
                image_string = get_signature()
                content = render_to_pdf(
                    "forms/disciplinary_expel_letter.html",
                    context={"object": activation.process, "signature": image_string},
                )
                activation.process.final_letter.save(
                    "final_letter.pdf", ContentFile(content), save=True
                )
                attachments = ["final_letter"]
            complete_step = "Executive Council Review"
            next_step = "Disciplinary Process Complete"
            state = "Complete"
            message = (
                "This is a notification that the Executive Council has reviewed "
                "your case and the outcome has been finalized.  "
                "Please see the attached document to learn that outcome."
            )
            fields = ["ec_approval", "ec_notes"]
        EmailProcessUpdate(
            activation,
            complete_step=complete_step,
            next_step=next_step,
            state=state,
            message=message,
            fields=fields,
            attachments=attachments,
            email_officers=True,
            extra_emails={
                activation.process.chapter.region.email,
                "Jim.Gaffney@thetatau.org",
                "riskchair@thetatau.org",
            },
        ).send()

    def email_regent_func(self, activation):
        """
        Form should be automatically emailed to the chapter regent on the day of the trial.

        If rejected, form 2 should be reopened so that the chapter can edit it again.
        """
        task_title = activation.flow_task.task_title
        host = settings.CURRENT_URL
        link = reverse(
            f"viewflow:forms:disciplinaryprocess:submit_form2",
            kwargs={"process_pk": activation.process.pk, "task_pk": activation.task.pk},
        )
        link = host + link
        if "Reject Chapter Fix" in task_title:
            fields = DisciplinaryForm1._meta.fields[:]
            fields2 = DisciplinaryForm2._meta.fields[:]
            fields.extend(fields2)
            fields.extend(["ed_process", "ed_notes"])
            fields.remove("charging_letter")
            fields.remove("minutes")
            fields.remove("results_letter")
            complete_step = "Executive Director Review"
            next_step = "Executive Director Review"
            state = "Executive Director Rejected"
            message = (
                "Unfortunately, I was unable to accept the outcome of your "
                f"chapter’s proceedings against {activation.process.user}.  "
                "The reason is listed at the bottom of this email next to "
                '"Executive Director Notes."  Please follow this link to '
                f"correct the issue and resubmit: <a href='{link}'>Disciplinary Process Form 2</a>"
            )
        else:
            fields = DisciplinaryForm1._meta.fields[:]
            fields.remove("charging_letter")
            complete_step = "Wait for Trial"
            next_step = "Complete Trial Outcome Form"
            state = "Pending Trial"
            message = (
                "This is a reminder that, per the form you filed on "
                f"{activation.process.created}, you are scheduled to have a trial for "
                f"{activation.process.user} on {activation.process.trial_date}.  "
                "Please remember to update us on the status "
                f"of this trial by filling out the form located at: <a href='{link}'>Disciplinary Process Form 2</a>"
                " If you have questions, please email or call the Central Office "
                "at central.office@thetatau.org // 512-472-1904."
            )
        EmailProcessUpdate(
            activation,
            complete_step=complete_step,
            next_step=next_step,
            state=state,
            message=message,
            fields=fields,
            direct_user=self.chapter_regent(activation),
        ).send()

    def chapter_regent(self, activation):
        (
            regent,
            vice_regent,
            _,
            _,
        ) = activation.process.chapter.get_current_officers_council_specific()
        if activation.process.user == regent:
            regent = vice_regent
        return regent

    def reschedule_func(self, activation):
        """
        rescheduling the form should 'snooze' until the new date
        """
        DisciplinaryProcessFlow.restart.run(old_activation=activation)

    def accept_done_func(self, activation):
        """
        If accepted with no action, generate PDFs of the two forms and email
            to CO for filing, complete workflow.
        """
        forms = activation.process.forms_pdf()
        CentralOfficeGenericEmail(
            message=f"Disciplinary Process complete for {object.user},"
            f"See attached documents to file.",
            attachments=[
                ContentFile(
                    forms,
                    name=f"{object.chapter.slug}_{object.user.user_id}_disciplinary_forms.pdf",
                )
            ],
        ).send()

    @classmethod
    def start_email_regent(cls, pk):
        process = DisciplinaryProcess.objects.get(pk=pk)
        cls.delay.run(process.get_task(cls.delay))

    @classmethod
    def start_send_ec(cls, pk):
        process = DisciplinaryProcess.objects.get(pk=pk)
        cls.delay_ec.run(process.get_task(cls.delay_ec))


@frontend.register
class ResignationFlow(Flow):
    process_class = ResignationProcess
    process_title = _("Resignation Process")
    process_description = _("This process is for member resignation.")

    start = flow.Start(
        ResignationCreateView, task_title=_("Submit Resignation Form")
    ).Next(this.email_signers)

    email_signers = flow.Handler(
        this.email_signers_func, task_title=_("Email Signers"),
    ).Next(this.assign_approval)

    assign_approval = flow.Split().Next(this.assign_o1).Next(this.assign_o2)

    assign_o1 = (
        flow.View(ResignationSignView, task_title=_("Officer1 Sign"))
        .Assign(lambda act: act.process.officer1)
        .Next(this.join_flow)
    )

    assign_o2 = (
        flow.View(ResignationSignView, task_title=_("Officer2 Sign"))
        .Assign(lambda act: act.process.officer2)
        .Next(this.join_flow)
    )

    join_flow = flow.Join().Next(this.email_complete)

    email_complete = flow.Handler(
        this.email_complete_func, task_title=_("Email Complete"),
    ).Next(this.end)

    end = flow.End(task_title=_("Complete"))

    def email_signers_func(self, activation):
        """
        Send emails to the signers
        :param activation:
        :return:
        """
        host = settings.CURRENT_URL
        for user_role in ["officer1", "officer2"]:
            user = getattr(activation.process, user_role)
            # You can not link directly to the task b/c it has not been assigned yet
            link = reverse("forms:resign_list")
            link = host + link
            EmailProcessUpdate(
                activation,
                complete_step="Submitted",
                next_step="Officer Review/Approval",
                state="Sign",
                message=f"{activation.process.user} has submitted for resignation from the chapter."
                f" Please review and complete the form here: <a href='{link}'>"
                f"Resignation List</a>",
                fields=[],
                attachments=["letter"],
                direct_user=user,
            ).send()

    def email_complete_func(self, activation):
        """
        Send emails to the signers
        :param activation:
        :return:
        """
        EmailProcessUpdate(
            activation,
            complete_step="Officer Acknowledge and Sign",
            next_step="Central Office Process",
            state="Submitted",
            message="",
            fields=[],
            email_officers=True,
            attachments=["letter"],
        ).send()
