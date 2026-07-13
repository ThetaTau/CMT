"""Email notifications for the nominations app (django-herald)."""

from herald import registry
from herald.base import EmailNotification

from core.models import NAT_OFFICERS_CHOICES

CENTRAL_OFFICE_EMAIL = "central.office@thetatau.org"

_POSITION_LABELS = dict(NAT_OFFICERS_CHOICES)


def _positions_display(nomination):
    labels = [_POSITION_LABELS.get(position, position) for position in nomination.recommended_positions]
    return ", ".join(labels)


@registry.register_decorator()
class NomineeConsentNotification(EmailNotification):
    """Sent to a nominee asking whether they want to serve, with a token link."""

    render_types = ["html"]
    template_name = "nominee_consent"
    subject = "You have been recommended to serve Theta Tau"

    def __init__(self, nomination, link):
        recipient = nomination.nominee_email_address
        self.to_emails = [recipient] if recipient else []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.subject = f"{nomination.nominator} recommended you to serve Theta Tau"
        self.context = {
            "nomination": nomination,
            "nominee_display": nomination.nominee_display,
            "nominator": nomination.nominator,
            "positions_display": _positions_display(nomination),
            "level_display": nomination.get_level_display(),
            "reason": nomination.reason,
            "consent_link": link,
        }


@registry.register_decorator()
class AppointmentLetterNotification(EmailNotification):
    """Emails the nominee that they have been appointed (VWI-9)."""

    render_types = ["html"]
    template_name = "appointment_letter"
    subject = "Your Theta Tau volunteer appointment"

    def __init__(self, nomination):
        recipient = nomination.nominee_email_address
        self.to_emails = [recipient] if recipient else []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.context = {
            "nomination": nomination,
            "nominee_display": nomination.nominee_display,
            "positions_display": _positions_display(nomination),
            "level_display": nomination.get_level_display(),
        }


@registry.register_decorator()
class RejectionThankYouNotification(EmailNotification):
    """ "Thank you, not at this time" note on a vetting/interview failure (VWI-10)."""

    render_types = ["html"]
    template_name = "rejection_thank_you"
    subject = "Thank you for your interest in serving Theta Tau"

    def __init__(self, nomination):
        recipient = nomination.nominee_email_address
        self.to_emails = [recipient] if recipient else []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.context = {
            "nomination": nomination,
            "nominee_display": nomination.nominee_display,
        }


@registry.register_decorator()
class DenialLetterNotification(EmailNotification):
    """Emails the denial letter to the nominee on a confirmation deny (VWI-10)."""

    render_types = ["html"]
    template_name = "denial_letter"
    subject = "Regarding your Theta Tau volunteer nomination"

    def __init__(self, nomination):
        recipient = nomination.nominee_email_address
        self.to_emails = [recipient] if recipient else []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.context = {
            "nomination": nomination,
            "nominee_display": nomination.nominee_display,
            "denial_reason": nomination.denial_reason,
        }


@registry.register_decorator()
class ChapterAppointmentNotification(EmailNotification):
    """Notifies the affected chapter(s) / region of an appointment (VWI-9)."""

    render_types = ["html"]
    template_name = "appointment_chapter"
    subject = "A member has been appointed to a Theta Tau volunteer role"

    def __init__(self, nomination, recipients):
        self.to_emails = list(recipients)
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.context = {
            "nomination": nomination,
            "nominee_display": nomination.nominee_display,
            "positions_display": _positions_display(nomination),
            "level_display": nomination.get_level_display(),
        }


@registry.register_decorator()
class NominationProgressNotification(EmailNotification):
    """Keeps the nominee informed as their nomination advances (WI #9)."""

    render_types = ["html"]
    template_name = "nomination_progress"
    subject = "Update on your Theta Tau nomination"

    def __init__(self, nomination, headline, message=""):
        recipient = nomination.nominee_email_address
        self.to_emails = [recipient] if recipient else []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.context = {
            "nomination": nomination,
            "nominee_display": nomination.nominee_display,
            "headline": headline,
            "message": message,
            "positions_display": _positions_display(nomination),
            "level_display": nomination.get_level_display(),
        }
