"""Template tags for displaying award badges + officer icons (AWI-10)."""

from django import template
from django.conf import settings

register = template.Library()


def _recipient_field(recipient):
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.regions.models import Region
    from thetatauCMT.users.models import User

    if isinstance(recipient, User):
        return "recipient_member"
    if isinstance(recipient, Chapter):
        return "recipient_chapter"
    if isinstance(recipient, Region):
        return "recipient_region"
    return None


def _history_url(recipient):
    """Award-history URL for a member / chapter recipient (AWI-12); None otherwise."""
    from django.urls import reverse

    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.users.models import User

    if isinstance(recipient, User):
        return reverse("awards:member_history", kwargs={"username": recipient.username})
    if isinstance(recipient, Chapter):
        return reverse("awards:chapter_history", kwargs={"slug": recipient.slug})
    return None


def award_grants_for(recipient, *, revoked=False):
    """Active (or revoked) award grants for a member / chapter / region."""
    from thetatauCMT.awards.models import AwardGrant

    field = _recipient_field(recipient)
    if field is None:
        return AwardGrant.objects.none()
    grants = AwardGrant.objects.filter(**{field: recipient})
    grants = grants.revoked() if revoked else grants.active()
    return grants.select_related("award_type", "cycle").order_by("-effective_date", "-id")


def award_badge_types_for(recipient):
    """Distinct award types (that have a badge image) the recipient holds."""
    seen = {}
    for grant in award_grants_for(recipient).filter(award_type__badge_image__gt=""):
        seen.setdefault(grant.award_type_id, grant.award_type)
    return list(seen.values())


def officer_badges_for(user):
    """Active OfficerBadges matching a member's current national-officer roles."""
    from thetatauCMT.awards.models import OfficerBadge
    from thetatauCMT.users.models import User

    if not isinstance(user, User):
        return []
    roles = set(user.current_roles or [])
    if not roles:
        return []
    return list(OfficerBadge.objects.filter(is_active=True, role__in=roles))


@register.simple_tag
def award_grant_count(recipient):
    """Count of active award grants held by a member / chapter / region."""
    return award_grants_for(recipient).count()


@register.inclusion_tag("awards/_inline_badges.html")
def inline_badges(recipient):
    """Render award badges (+ officer icons for members) inline next to a name."""
    return {
        "award_badges": award_badge_types_for(recipient),
        "officer_badges": officer_badges_for(recipient),
    }


@register.inclusion_tag("awards/_awards_section.html")
def awards_section(recipient, show_revoked=None):
    """Render the awards card for a member / chapter / region profile."""
    if show_revoked is None:
        show_revoked = getattr(settings, "AWARDS_SHOW_REVOKED", False)
    return {
        "active_grants": list(award_grants_for(recipient)),
        "revoked_grants": list(award_grants_for(recipient, revoked=True)) if show_revoked else [],
        "show_revoked": show_revoked,
        "history_url": _history_url(recipient),
    }
