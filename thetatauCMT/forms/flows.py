from viewflow import flow, frontend
from viewflow.base import this, Flow
from viewflow.compat import _
from viewflow.flow import views as flow_views
from .models import PrematureAlumnus
from .views import PrematureAlumnusCreateView
from users.models import User


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

    start_officer = (
        flow.Start(
            flow_views.CreateProcessView,
            fields=['form', 'user'],
            task_title=_('Request Premature Alumnus Other Member'))
        .Permission(auto_create=True)
        .Next(this.exec_approve)
    )

    pending_status = (
        flow.Handler(
            this.set_status_assign_email,
            task_title=_('Set pending status, send email, and assign officers'),
        )
        .Next(this.officer_assign)
    )

    officer_assign = (
        flow.Split()
        .Next(this.officer1_approve)
        .Next(this.officer2_approve)
    )

    officer1_approve = (
        flow.View(
            flow_views.UpdateProcessView, fields=['officer1_ack', 'officer1_comments'],
            task_title=_('Chapter Officer 1 Review'),
            task_description=_("Acknowledgement required for {{ process.user }} Premature Alumnus request"),
            task_result_summary=_("Request was {{ process.officer1_ack|yesno:'Acknowledged,Rejected' }}"))
        .Assign(lambda act: act.process.officers.first())
        .Next(this.officer_review_complete)
    )

    officer2_approve = (
        flow.View(
            flow_views.UpdateProcessView, fields=['officer2_ack', 'officer2_comments'],
            task_title=_('Chapter Officer 2 Review'),
            task_description=_("Acknowledgement required for {{ process.user }} Premature Alumnus request"),
            task_result_summary=_("Request was {{ process.officer2_ack|yesno:'Acknowledged,Rejected' }}"))
        .Assign(lambda act: act.process.officers.last())
        .Next(this.officer_review_complete)
    )

    officer_review_complete = flow.Join().Next(this.exec_approve)

    exec_approve = (
        flow.View(
            flow_views.UpdateProcessView, fields=['approved_exec', 'exec_comments'],
            task_title=_('Executive Director Review'),
            task_description=_("Pre Alumn review for {{ process.user }}"),
            task_result_summary=_("Messsage was {{ process.approved_exec|yesno:'Approved,Rejected' }}"))
        .Assign(lambda act: User.objects.get(username="venturafranklin@gmail.com"))
        .Next(this.check_approve)
    )

    check_approve = (
        flow.If(
            cond=lambda act: act.process.approved_exec,
            task_title=_('Premature Alumnus Approvement check'),
        )
        .Then(this.alumni_status)
        .Else(this.send)
    )

    alumni_status = (
        flow.Handler(
            this.set_alumni_status,
            task_title=_('Set status alumni'),
        )
        .Next(this.send)
    )

    send = (
        flow.Handler(
            this.send_approval_complete,
            task_title=_('Send approval complete message'),
        )
        .Next(this.complete)
    )

    complete = flow.End(
        task_title=_('Complete'),
    )

    def set_status_assign_email(self, activation):
        """
        Need to set the pending status
        Email the user the form was received
        Assign officers to review
        :param activation:
        :return:
        """
        user = activation.process.created_by
        chapter = activation.process.created_by.chapter
        regent = chapter.get_current_officers_council(combine=False)[0].filter(roles__role="regent").first()
        vice_regent = chapter.get_current_officers_council(combine=False)[0].filter(roles__role="vice regent").first()
        scribe = chapter.get_current_officers_council(combine=False)[0].filter(roles__role="scribe").first()
        if user != regent:
            activation.process.officers.add(regent)
        else:
            activation.process.officers.add(scribe)
        if user != vice_regent:
            activation.process.officers.add(vice_regent)
        else:
            activation.process.officers.add(scribe)

    def set_alumni_status(self, activation):
        print(activation.process.created_by)

    def send_approval_complete(self, activation):
        print(activation.process.created_by)
