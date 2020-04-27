import datetime
from django.utils.decorators import method_decorator
from viewflow import flow, frontend
from viewflow.base import this, Flow
from viewflow.compat import _
from viewflow.flow import views as flow_views
from core.models import forever
from core.flows import AutoAssignUpdateProcessView, NoAssignView
from .models import PrematureAlumnus, InitiationProcess, Convention, PledgeProcess
from .views import PrematureAlumnusCreateView, ConventionCreateView,\
    ConventionSignView, FilterableFlowViewSet
from .notifications import EmailProcessUpdate, EmailConventionUpdate
from users.models import User, UserStatusChange


@frontend.register
class PrematureAlumnusFlow(Flow):
    process_class = PrematureAlumnus
    process_title = _('Premature Alumnus Process')
    process_description = _('This process is for premature alumnus processing.')

    start = (
        flow.Start(
            PrematureAlumnusCreateView,
            task_title=_('Request Premature Alumnus'))
        .Permission(auto_create=True)
        .Next(this.pending_status)
    )

    pending_status = (
        flow.Handler(
            this.set_status_email,
            task_title=_('Set pending status, send email.'),
        )
        .Next(this.exec_approve)
    )

    exec_approve = (
        flow.View(
            flow_views.UpdateProcessView, fields=['approved_exec', 'exec_comments',],
            task_title=_('Executive Director Review'),
            task_description=_("Pre Alumn Executive Director Review"),
            task_result_summary=_("Messsage was {{ process.approved_exec|yesno:'Approved,Rejected' }}"))
        .Assign(lambda act: User.objects.get(username="Jim.Gaffney@thetatau.org"))
        .Next(this.check_approve)
    )

    check_approve = (
        flow.If(
            cond=lambda act: act.process.approved_exec,
            task_title=_('Premature Alumnus Approvement check'),
        )
        .Then(this.alumni_status)
        .Else(this.pending_undo)
    )

    alumni_status = (
        flow.Handler(
            this.set_alumni_status,
            task_title=_('Set status alumni'),
        )
        .Next(this.send)
    )

    pending_undo = (
        flow.Handler(
            this.pending_undo_func,
            task_title=_('Set status active'),
        )
        .Next(this.send)
    )

    send = (
        flow.Handler(
            this.send_approval_complete,
            task_title=_('Send request complete message'),
        )
        .Next(this.complete)
    )

    complete = flow.End(
        task_title=_('Complete'),
        task_result_summary=_("Request was {{ process.approved_exec|yesno:'Approved,Rejected' }}")
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
        active = user.status.order_by('-end').filter(status='active').first()
        if not active:
            print(f"There was no active status for user {user}")
            UserStatusChange(
                user=user,
                status='active',
                created=created,
                start=created - datetime.timedelta(days=365),
                end=created,
            ).save()
        else:
            active.end = created
            active.created = created
            active.save()
        alumnipends = user.status.filter(status='alumnipend')
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
                status='alumnipend',
                start=created,
                end=forever(),
            ).save()
        EmailProcessUpdate(
            activation, "Premature Alumnus Request", "Executive Director Review",
            "Submitted",
            "Your chapter has submitted a premature alumnus form on your behalf." +
            " Once the Central Office processes " +
            "the form, you will receive an email confirming your change in status.",
            ['good_standing', 'financial', 'semesters', 'lifestyle',
             'consideration', 'prealumn_type', 'vote', ]
        ).send()

    def pending_undo_func(self, activation):
        user = activation.process.user
        alumnipends = user.status.filter(status='alumnipend')
        if alumnipends:
            for alumnipend in alumnipends:
                alumnipend.delete()

    def set_alumni_status(self, activation):
        user = activation.process.user
        alumnipend = user.status.order_by('-end').filter(status='alumnipend').first()
        created = activation.task.created
        if not alumnipend:
            print(f"There was no alumnipend status for user {user}")
            UserStatusChange(
                user=user,
                status='alumnipend',
                created=created,
                start=created - datetime.timedelta(days=365),
                end=created,
            ).save()
        else:
            alumnipend.end = created
            alumnipend.save()
        alumnis = user.status.filter(status='alumni')
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
                status='alumni',
                start=created,
                end=forever(),
            ).save()

    def send_approval_complete(self, activation):
        if activation.process.approved_exec:
            state = 'Approved'
        else:
            state = 'Rejected'
        EmailProcessUpdate(
            activation, "Executive Director Review", "Complete",
            state, "", ['approved_exec', 'exec_comments', ]
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
    process_title = _('Initiation Process')
    process_description = _('This process is for initiation form processing.')
    summary_template = "{{ flow_class.process_title }} - {{ process.chapter }}"

    start = flow.StartFunction(
        this.create_flow, activation_class=flow.nodes.ManagedStartViewActivation
    ).Next(this.invoice_chapter)
    start_manual = (
        flow.Start(
            flow_views.CreateProcessView, fields=["chapter", ])
        .Permission(auto_create=True)
        .Next(this.invoice_chapter)
    )

    invoice_chapter = (
        NoAssignView(
            AutoAssignUpdateProcessView, fields=['invoice', ],
            task_title=_('Invoice Chapter'),
            task_description=_("Send invoice to chapter"),
            task_result_summary=_("Invoice was sent to chapter"))
        .Permission('auth.central_office')
        .Next(this.invoice_payment)
    )

    send_invoice = (
        flow.Handler(
            this.send_invoice_func,
            task_title=_('Send Invoice'),
        )
        .Next(this.invoice_payment)
    )

    invoice_payment = (
        NoAssignView(
            AutoAssignUpdateProcessView,
            task_title=_('Invoice Payment'),
            task_description=_("Invoice payment by chapter"),
            task_result_summary=_("Invoice paid by chapter"))
        .Permission('auth.central_office')
        .Next(this.invoice_payment_email)
    )

    invoice_payment_email = (
        flow.Handler(
            this.send_invoice_payment_email,
            task_title=_('Send Invoice Payment Email'),
        )
        .Next(this.order_complete)
    )

    order_complete = (
        NoAssignView(
            AutoAssignUpdateProcessView,
            task_title=_('Order Complete'),
            task_description=_("Badge/shingle placing order"),
            task_result_summary=_("Badge/shingle order has been placed"))
        .Permission('auth.central_office')
        .Next(this.send_order)
    )

    send_order = (
        flow.Handler(
            this.send_order_func,
            task_title=_('Send Order'),
        )
        .Next(this.complete)
    )

    complete = flow.End(
        task_title=_('Complete'),
        task_result_summary=_("Initiation Process Complete")
    )

    @method_decorator(flow.flow_start_func)
    def create_flow(self, activation, initiations, request=None, created=None, **kwargs):
        activation.process.chapter = initiations[0].user.chapter
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
        member_list = ', '.join(member_list)
        EmailProcessUpdate(
            activation, "Initiation Report Submitted",
            "Central Office Processing & Invoice Generation",
            "Submitted",
            "Your chapter has submitted an initiation report." +
            " Once the Central Office processes the report, an invoice will be generated" +
            " and will be sent to your chapter on the last business day of this month.",
            [{'members': member_list}, ]
        ).send()
        return activation

    def send_invoice_func(self, activation):
        ...

    def send_invoice_payment_email(self, activation):
        member_list = activation.process.initiations.values_list('user__email', flat=True)
        member_list = ', '.join(member_list)
        EmailProcessUpdate(
            activation, "Initiation Invoice Paid",
            "Central Office Badge/Shingle Order",
            "Payment Received",
            "Your chapter has paid an initiation invoice." +
            " Once the Central Office processes the payment, an order will be sent" +
            " to the jeweler/shingler.",
            [{'members': member_list}, 'invoice', ]
        ).send()

    def send_order_func(self, activation):
        member_list = activation.process.initiations.values_list('user__email', flat=True)
        member_list = ', '.join(member_list)
        EmailProcessUpdate(
            activation, "Badge/Shingles Order Submitted",
            "Initiation Process Complete",
            "Badges/Shingles Ordered",
            "A badges and shingles order has been sent to the vendor.",
            [{'members': member_list}, 'invoice', ]
        ).send()


@frontend.register
class ConventionFlow(Flow):
    process_class = Convention
    process_title = _('Convention Process')
    process_description = _('This process is for delegeate and alternate for convention.')

    start = (
        flow.Start(
            ConventionCreateView,
            task_title=_('Submit Convention Form'))
        .Next(this.email_signers)
    )

    email_signers = (
        flow.Handler(
            this.email_signers_func,
            task_title=_('Email Signers'),
        )
        .Next(this.assign_approval)
    )

    assign_approval = (
        flow.Split(
        ).Next(
            this.assign_del,
        ).Next(
            this.assign_alt,
        ).Next(
            this.assign_o1
        ).Next(
            this.assign_o2
        )
    )

    assign_del = (
        flow.View(
            ConventionSignView,
            task_title=_('Delegate Sign'))
        .Assign(lambda act: act.process.delegate)
        .Next(this.join_flow)
    )

    assign_alt = (
        flow.View(
            ConventionSignView,
            task_title=_('Alternate Sign'))
        .Assign(lambda act: act.process.alternate)
        .Next(this.join_flow)
    )

    assign_o1 = (
        flow.View(
            ConventionSignView,
            task_title=_('Officer1 Sign'))
        .Assign(lambda act: act.process.officer1)
        .Next(this.join_flow)
    )

    assign_o2 = (
        flow.View(
            ConventionSignView,
            task_title=_('Officer2 Sign'))
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
        for user_role in ['delegate', 'alternate', 'officer1', 'officer2']:
            user = getattr(activation.process, user_role)
            EmailConventionUpdate(
                activation, user, "Convention Credential Form Submitted",
            ).send()


@frontend.register
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
    process_title = _('Pledge Process')
    process_description = _('This process is for pledge form processing.')
    summary_template = "{{ flow_class.process_title }} - {{ process.chapter }}"

    start = flow.StartFunction(
        this.create_flow, activation_class=flow.nodes.ManagedStartViewActivation
    ).Next(this.invoice_chapter)

    invoice_chapter = (
        NoAssignView(
            AutoAssignUpdateProcessView, fields=['invoice', ],
            task_title=_('Invoice Chapter'),
            task_description=_("Send invoice to chapter"),
            task_result_summary=_("Invoice was sent to chapter"))
        .Permission('auth.central_office')
        .Next(this.send_invoice)
    )

    send_invoice = (
        flow.Handler(
            this.send_invoice_func,
            task_title=_('Send Invoice'),
        )
        .Next(this.invoice_payment)
    )

    invoice_payment = (
        NoAssignView(
            AutoAssignUpdateProcessView,
            task_title=_('Invoice Payment'),
            task_description=_("Invoice payment by chapter"),
            task_result_summary=_("Invoice paid by chapter"))
        .Permission('auth.central_office')
        .Next(this.invoice_payment_email)
    )

    invoice_payment_email = (
        flow.Handler(
            this.send_invoice_payment_email,
            task_title=_('Send Invoice Payment Email'),
        )
        .Next(this.complete)
    )

    complete = flow.End(
        task_title=_('Complete'),
        task_result_summary=_("Pledge Process Complete")
    )

    @method_decorator(flow.flow_start_func)
    def create_flow(self, activation, chapter, request=None, created=None, **kwargs):
        activation.process.chapter = chapter
        activation.process.save()
        if request is not None:
            activation.prepare(None, user=request.user)
        else:
            activation.prepare()
        activation.done()
        if created is not None:
            activation.process.created = created
            activation.process.save()
        return activation

    def send_invoice_func(self, activation):
        ...

    def send_invoice_payment_email(self, activation):
        member_list = activation.process.pledges.values_list('email_school', flat=True)
        member_list = ', '.join(member_list)
        EmailProcessUpdate(
            activation, "Pledge Invoice Paid",
            "Complete",
            "Payment Received",
            "Your chapter has paid a pledge invoice.",
            [{'members': member_list}, 'invoice', ]
        ).send()
