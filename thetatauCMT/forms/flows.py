import datetime
from django.utils.decorators import method_decorator
from viewflow import flow, frontend
from viewflow.base import this, Flow
from viewflow.compat import _
from viewflow.flow import views as flow_views
from core.models import forever
from .models import PrematureAlumnus, InitiationProcess
from .views import PrematureAlumnusCreateView
from .notifications import EmailProcessUpdate
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


@frontend.register
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

    # start = flow.StartFunction(this.create_flow).Next(this.invoice_chapter)
    start = (
        flow.Start(
            flow_views.CreateProcessView, fields=["test"])
        .Permission(auto_create=True)
        .Next(this.invoice_chapter)
    )

    invoice_chapter = (
        flow.View(
            flow_views.UpdateProcessView,
            task_title=_('Invoice Chapter'),
            task_description=_("Send invoice to chapter"),
            task_result_summary=_("Invoice was sent to chapter"))
        .Assign(lambda act: User.objects.get(username="venturafranklin@gmail.com"))
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
        flow.View(
            flow_views.UpdateProcessView,
            task_title=_('Invoice Payment'),
            task_description=_("Invoice payment by chapter"),
            task_result_summary=_("Invoice paid by chapter"))
        .Assign(lambda act: User.objects.get(username="venturafranklin@gmail.com"))
        .Next(this.send_order)
    )

    send_order = (
        flow.Handler(
            this.send_order_func,
            task_title=_('Send Order'),
        )
        .Next(this.order_complete)
    )

    order_complete = (
        flow.View(
            flow_views.UpdateProcessView,
            task_title=_('Order Complete'),
            task_description=_("Badge/shingle placing order"),
            task_result_summary=_("Badge/shingle order has been placed"))
        .Assign(lambda act: User.objects.get(username="venturafranklin@gmail.com"))
        .Next(this.complete)
    )

    complete = flow.End(
        task_title=_('Complete'),
        task_result_summary=_("Initiation Process Complete")
    )

    @method_decorator(flow.flow_start_func)
    def create_flow(self, activation, initiations, **kwargs):
        activation.prepare()
        for initiation in initiations:
            activation.process.initiations.add(initiation)
        activation.done()
        return activation

    def send_invoice_func(self, activation):
        ...

    def send_order_func(self, activation):
        ...
