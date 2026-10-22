from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import dateformat, timezone
from herald import registry
from herald.base import EmailNotification

from .services import set_password_url


@registry.register_decorator()
class EmailSupportWelcome(EmailNotification):
    """The account email for a new Chapter Support Specialist staff account (CSSWI-5).

    It only covers signing in. Assignments are announced by national, not the CMT (Q17).
    """

    template_name = "css_welcome"
    subject = "Your Theta Tau Chapter Management Tool account"

    def __init__(self, user):
        self.to_emails = {user.email}
        self.cc = []
        self.reply_to = ["central.office@thetatau.org"]
        self.context = {
            "user": user,
            "set_password_url": set_password_url(user),
            "reset_url": f"{settings.CURRENT_URL}{reverse('account_reset_password')}?{urlencode({'email': user.email})}",
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from thetatauCMT.users.models import User

        return [User.objects.order_by("?")[0]]


@registry.register_decorator()
class EmailSupportDailyDigest(EmailNotification):
    """The emails a CSS gets only through the digest, in full, by chapter (Q25 C, S17)."""

    render_types = ["html"]
    template_name = "css_daily_digest"

    def __init__(self, user, entries, when):
        from .digests import daily_sections

        sections, already_sent = daily_sections(entries)
        day = timezone.localtime(when).date()
        self.to_emails = {user.email}
        self.cc = []
        self.reply_to = ["central.office@thetatau.org"]
        self.subject = f"Chapter Support Specialist digest, {dateformat.format(day, 'F j, Y')}"
        self.context = {
            "user": user,
            "sections": sections,
            "already_sent": already_sent,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from .models import SupportDigestEntry

        entry = SupportDigestEntry.objects.select_related("user", "chapter").order_by("-pk").first()
        entries = list(entry.user.support_digest_entries.select_related("chapter").order_by("chapter__name")[:10])
        return [entry.user, entries, timezone.now()]


@registry.register_decorator()
class EmailSupportMonthlyDigest(EmailNotification):
    """Each chapter's month: last month's emails, and what is still open (Q14)."""

    render_types = ["html"]
    template_name = "css_monthly_digest"

    def __init__(self, user, period_start, sections):
        self.to_emails = {user.email}
        self.cc = []
        self.reply_to = ["central.office@thetatau.org"]
        month = dateformat.format(period_start, "F Y")
        self.subject = f"Chapter Support Specialist monthly digest, {month}"
        self.context = {
            "user": user,
            "month": month,
            "sections": sections,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from core.models import previous_month_period

        from .digests import chapter_month_summary
        from .services import css_chapters, current_css_users

        user = current_css_users().first()
        today = timezone.localdate()
        sections = [chapter_month_summary(chapter, [], today) for chapter in css_chapters(user)]
        return [user, previous_month_period(today)[0], sections]
