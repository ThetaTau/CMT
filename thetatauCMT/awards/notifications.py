"""Email notifications for the awards app (django-herald)."""

from django.conf import settings
from django.urls import NoReverseMatch, reverse
from herald import registry
from herald.base import EmailNotification

CENTRAL_OFFICE_EMAIL = "central.office@thetatau.org"


def _award_review_url(process):
    """Absolute URL where the approver reviews a nomination.

    The submit-time notification fires before the review task exists, so this
    links to the process detail page (falling back to the workflow inbox).
    """
    host = getattr(settings, "CURRENT_URL", "").rstrip("/")
    try:
        path = reverse("viewflow:awards:awardnomination:detail", args=[process.pk])
    except NoReverseMatch:
        path = "/workflow/"
    return f"{host}{path}"


def _digest_unsubscribe_footer(recipient):
    """Per-recipient unsubscribe footer HTML for the monthly award digest."""
    if recipient is None:
        return ""
    from thetatauCMT.awards.digest import DIGEST_CATEGORY_SLUG
    from thetatauCMT.users.notifications import _unsubscribe_footer

    return _unsubscribe_footer(recipient, category=DIGEST_CATEGORY_SLUG)


def grant_notification_recipients(grant):
    """Emails to notify when a grant is created: the recipient(s) + relevant officers.

    * member  -> the member's emails + their chapter's officer emails
    * chapter -> the entire chapter (all current members) + officer emails
    * region  -> the region's directors + region mailbox
    """
    emails = set()
    recipient = grant.recipient
    kind = grant.recipient_kind
    if recipient is None:
        return []
    if kind == "member":
        # The recipient member plus their chapter's officers.
        emails |= {email for email in recipient.emails if email}
        chapter = getattr(recipient, "chapter", None)
        if chapter is not None:
            emails |= chapter.council_emails()
    elif kind == "chapter":
        # A chapter award goes to the entire chapter (all current members) + officers.
        emails |= recipient.council_emails()
        member_emails = recipient.current_members().values_list("email", "email_school")
        emails |= {email for pair in member_emails for email in pair if email}
    elif kind == "region":
        emails |= {director.email for director in recipient.directors.all() if director.email}
        if getattr(recipient, "email", ""):
            emails.add(recipient.email)
    return sorted({email for email in emails if email})


@registry.register_decorator()
class AwardGrantedNotification(EmailNotification):
    """Notify the recipient + relevant officers that an award was granted."""

    render_types = ["html"]
    template_name = "award_granted"

    def __init__(self, grant):
        self.to_emails = grant_notification_recipients(grant)
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.subject = f"Award granted: {grant.award_type} \u2014 {grant.recipient_display}"
        self.context = {
            "grant": grant,
            "award": grant.award_type,
            "description": grant.award_type.description,
            "recipient": grant.recipient_display,
            "cycle": grant.cycle,
            "effective_date": grant.effective_date,
            "reason": grant.reason,
        }

    @staticmethod
    def get_demo_args():
        from .models import AwardGrant

        return [AwardGrant.objects.order_by("-id").first()]


@registry.register_decorator()
class AwardNominationSubmittedNotification(EmailNotification):
    """Notify the configured approver that a nomination is waiting for review."""

    render_types = ["html"]
    template_name = "award_nomination_submitted"

    def __init__(self, nomination, approver):
        self.to_emails = sorted({email for email in getattr(approver, "emails", set()) if email}) if approver else []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.subject = f"Award nomination to review: {nomination.award_type} \u2014 {nomination.recipient_display}"
        self.context = {
            "nomination": nomination,
            "award": nomination.award_type,
            "description": nomination.award_type.description,
            "recipient": nomination.recipient_display,
            "nominator": nomination.nominator,
            "justification": nomination.justification,
            "review_url": _award_review_url(nomination),
        }

    @staticmethod
    def get_demo_args():
        from thetatauCMT.users.models import User
        from .models import AwardNominationProcess

        nomination = AwardNominationProcess.objects.order_by("-id").first()
        approver = User.objects.order_by("?").first()
        return [nomination, approver]


@registry.register_decorator()
class AwardDigestNotification(EmailNotification):
    """Monthly digest of granted awards to a configured audience."""

    render_types = ["html"]
    template_name = "award_digest"

    def __init__(self, grants, period_start, period_end, recipient):
        grants = list(grants)
        self.recipient = recipient
        self.to_emails = sorted({email for email in getattr(recipient, "emails", set()) if email})
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.subject = f"Theta Tau Awards \u2014 {period_start:%B %Y} ({len(grants)} awards)"
        self.context = {
            "grants": grants,
            "period_start": period_start,
            "period_end": period_end,
            "count": len(grants),
            "recipient": recipient,
            "unsubscribe_footer": _digest_unsubscribe_footer(recipient),
        }

    @staticmethod
    def get_demo_args():
        from core.models import previous_month_period
        from thetatauCMT.users.models import User
        from .models import AwardGrant

        start, end = previous_month_period()
        grants = list(AwardGrant.objects.active().select_related("award_type", "cycle")[:10])
        return [grants, start, end, User.objects.order_by("?").first()]
