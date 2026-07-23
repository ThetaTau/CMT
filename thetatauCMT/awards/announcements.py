"""Home-page announcement creation for award grants (AWI-9)."""

from datetime import timedelta

from django.utils import timezone

from thetatauCMT.announcements.models import Announcement

ANNOUNCEMENT_DAYS_VISIBLE = 30


def create_grant_announcement(grant, days_visible=ANNOUNCEMENT_DAYS_VISIBLE):
    """Create a home-page :class:`Announcement` recognizing an award grant."""
    now = timezone.now()
    title = f"Award: {grant.award_type} \u2014 {grant.recipient_display}"
    content = (
        f"<p>{grant.recipient_display} received the <strong>{grant.award_type}</strong> " f"award ({grant.cycle}).</p>"
    )
    if grant.reason:
        content += f"<p>{grant.reason}</p>"
    return Announcement.objects.create(
        title=title,
        content=content,
        publish_start=now,
        publish_end=now + timedelta(days=days_visible),
    )
