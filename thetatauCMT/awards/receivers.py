import logging

from .certificates import maybe_generate_certificate

logger = logging.getLogger(__name__)


def on_award_granted(sender, grant, actor=None, **kwargs):
    """Auto-generate a certificate when the award type is configured to do so.

    Connected to the :data:`~thetatauCMT.awards.signals.award_granted` signal, so
    both the direct-grant (AWI-5) and nomination-approval (AWI-7) paths trigger
    it uniformly.
    """
    maybe_generate_certificate(grant, created_by=actor)


def notify_on_award_granted(sender, grant, actor=None, **kwargs):
    """Notify the recipient / officers and create a home-page announcement.

    Both steps are best-effort: a failure is logged but never propagated, so it
    can never break the grant path.
    """
    from .announcements import create_grant_announcement
    from .notifications import AwardGrantedNotification, grant_notification_recipients

    try:
        if grant_notification_recipients(grant):
            AwardGrantedNotification(grant).send()
    except Exception:
        logger.exception("Award granted notification failed for grant %s", grant.pk)
    try:
        create_grant_announcement(grant)
    except Exception:
        logger.exception("Award announcement failed for grant %s", grant.pk)
