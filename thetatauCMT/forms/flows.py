from viewflow import flow, frontend
from viewflow.base import this, Flow
from viewflow.compat import _
from viewflow.flow import views as flow_views
from .models import PrematureAlumnus
from users.models import User


@frontend.register
class PrematureAlumnusFlow(Flow):
    process_class = PrematureAlumnus
    process_title = _('Premature Alumnus Process')
    process_description = _('This process is for the approval of premature alumnus forms.')
    start = (
        flow.Start(
            flow_views.CreateProcessView,
            fields=['form'],
            task_title=_('Request Premature Alumnus'))
        .Permission(auto_create=True)
        .Next(this.approve)
    )

    approve = (
        flow.View(
            flow_views.UpdateProcessView, fields=['approved'],
            task_title=_('Approve Premature Alumnus'),
            task_description=_("Approvement required for {{ process.user }}"),
            task_result_summary=_("Messsage was {{ process.approved|yesno:'Approved,Rejected' }}"))
        .Assign(lambda act: User.objects.get(username="venturafranklin@gmail.com"))
        .Next(this.check_approve)
    )

    check_approve = (
        flow.If(
            cond=lambda act: act.process.approved,
            task_title=_('Premature Alumnus Approvement check'),
        )
        .Then(this.send)
        .Else(this.end)
    )

    send = (
        flow.Handler(
            this.send_hello_world_request,
            task_title=_('Send message'),
        )
        .Next(this.end)
    )

    end = flow.End(
        task_title=_('End'),
    )

    def send_hello_world_request(self, activation):
        print(activation.process.text)
