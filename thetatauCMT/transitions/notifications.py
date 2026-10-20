"""TRWI-4: reminder emails for Transition Report obligations.

Recipients are resolved by the caller (services.send_due_date_reminders /
send_seasonal_reminder) -- these classes only render what they're given,
matching thetatauCMT.users.notifications.OfficerUpdateReminder's split of
"service decides who", "notification class just sends".
"""

from django.conf import settings
from herald import registry
from herald.base import EmailNotification


def _chapter_display_name(chapter):
    return chapter.name if chapter.candidate_chapter else chapter.name + " Chapter"


@registry.register_decorator()
class TransitionReportDueReminder(EmailNotification):
    """Per-obligation due-date reminder (TRWI-4 mechanism 1)."""

    render_types = ["html"]
    template_name = "transition_report_due_reminder"
    subject = "Transition Report reminder"

    def __init__(self, obligation, emails, past_due, escalate_to_rd):
        self.to_emails = {email for email in emails if email}
        self.cc = []
        self.reply_to = ["central.office@thetatau.org"]
        chapter_name = _chapter_display_name(obligation.chapter)
        self.subject = f"Transition Report reminder: {obligation.position_key.title()} ({chapter_name})"
        report = getattr(obligation, "report", None)
        self.context = {
            "obligation": obligation,
            "chapter": chapter_name,
            "position_key": obligation.position_key,
            "due_date": obligation.due_date,
            "past_due": past_due,
            "escalate_to_rd": escalate_to_rd,
            # A saved draft is not a submission: the reminders keep coming.
            "has_draft": report is not None and report.status == report.Status.draft.value[0],
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from .models import ReportObligation

        obligation = ReportObligation.objects.order_by("?").first()
        return [obligation, {"demo@example.com"}, False, False]


@registry.register_decorator()
class TransitionReportSeasonalReminder(EmailNotification):
    """Once-per-semester broadcast nudge to a user with open obligations (TRWI-4 mechanism 2)."""

    render_types = ["html"]
    template_name = "transition_report_seasonal_reminder"
    subject = "Transition Report reminder"

    def __init__(self, user, obligations):
        self.to_emails = {email for email in user.emails if email}
        self.cc = []
        self.reply_to = ["central.office@thetatau.org"]
        self.context = {
            "user": user,
            "obligations": list(obligations),
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from thetatauCMT.users.models import User

        from .models import ReportObligation

        user = User.objects.order_by("?").first()
        obligations = ReportObligation.objects.filter(officer=user, status="open")
        return [user, obligations]


@registry.register_decorator()
class HandoffPacketAvailable(EmailNotification):
    """New-officeholder notice that predecessor Transition Reports exist to
    read (TRWI-7). Fired once per role taken (services.send_handoff_notices)
    -- the packet view always reflects the current full history, so this is
    a one-time "come look" nudge, not a recurring reminder.
    """

    render_types = ["html"]
    template_name = "transition_handoff_packet_available"
    subject = "Transition Reports are available for your new position"

    def __init__(self, user, position_key, chapter, report_count):
        self.to_emails = {email for email in user.emails if email}
        self.cc = []
        self.reply_to = ["central.office@thetatau.org"]
        chapter_name = _chapter_display_name(chapter)
        self.subject = f"Transition Reports available: {position_key.title()} ({chapter_name})"
        self.context = {
            "user": user,
            "position_key": position_key,
            "chapter_name": chapter_name,
            "chapter_pk": chapter.pk,
            "report_count": report_count,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from thetatauCMT.users.models import User

        user = User.objects.order_by("?").first()
        return [user, "treasurer", user.chapter, 3]
