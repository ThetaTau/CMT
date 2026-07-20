"""Monthly award digest (AWI-9): aggregate a period's grants into one email.

Idempotent: a period that already has an :class:`AwardDigestRun` is skipped
(unless forced), so the command is safe to re-run.
"""

from django.utils import timezone

from core.models import ACTIVE_STATUSES

from .models import AwardDigestRun, AwardGrant
from .notifications import AwardDigestNotification

# Alumni statuses that also receive the digest (matches the eligibility engine).
ALUMNI_STATUSES = ["alumni", "alumniCC"]

# Unsubscribe category slug -- registered in thetatauCMT.users.unsubscribe.
DIGEST_CATEGORY_SLUG = "award_digest"


def grants_in_period(period_start, period_end):
    """Active grants whose ``effective_date`` falls within the period."""
    return (
        AwardGrant.objects.active()
        .filter(effective_date__gte=period_start, effective_date__lte=period_end)
        .select_related("award_type", "cycle")
        .order_by("effective_date", "id")
    )


def digest_recipients():
    """Active + alumni members who have not opted out of the award digest."""
    from thetatauCMT.users.models import User

    statuses = list(ACTIVE_STATUSES) + ALUMNI_STATUSES
    return (
        User.objects.filter(current_status__in=statuses)
        .exclude(unsubscribe_email=True)
        .exclude(no_contact=True)
        .exclude(unsubscribe_categories__contains=[DIGEST_CATEGORY_SLUG])
    )


def send_award_digest(period_start, period_end, *, sent_by=None, force=False, dry_run=False):
    """Send the digest for a period. Returns the :class:`AwardDigestRun` or ``None``.

    Skips (returns ``None``) when the period already has a run and ``force`` is
    not set -- the idempotency guard.
    """
    already = AwardDigestRun.objects.filter(period_start=period_start, period_end=period_end).exists()
    if already and not force:
        return None
    grants = list(grants_in_period(period_start, period_end))
    if dry_run:
        return None
    for recipient in digest_recipients().iterator():
        notification = AwardDigestNotification(grants, period_start, period_end, recipient)
        if notification.to_emails:
            notification.send()
    run, _created = AwardDigestRun.objects.update_or_create(
        period_start=period_start,
        period_end=period_end,
        defaults={"grant_count": len(grants), "sent_by": sent_by, "sent_at": timezone.now()},
    )
    return run
