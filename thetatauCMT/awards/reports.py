"""Award reporting queries (AWI-12).

Read-only query helpers that back the CSV / Excel exports and the award-history
views. Each returns an ``AwardGrant`` queryset with the display relations
pre-fetched. "By chapter" / "by region" match the grant's *associated* entity
(the same rule the public directory filters use): a chapter matches grants to
that chapter and to its members; a region matches grants to that region, to its
chapters, and to members whose chapter is in it.

History queries are ordered chronologically by ``effective_date`` (so backdated
grants sort into their historical place) and include revoked grants by default
so the full record is visible.
"""

from django.db.models import Q

from .models import AwardGrant

_DISPLAY_RELATIONS = (
    "award_type",
    "cycle",
    "granted_by",
    "recipient_member",
    "recipient_member__chapter",
    "recipient_member__chapter__region",
    "recipient_chapter",
    "recipient_chapter__region",
    "recipient_region",
)


def _base(include_revoked):
    qs = AwardGrant.objects.select_related(*_DISPLAY_RELATIONS)
    return qs if include_revoked else qs.active()


def all_grants(*, include_revoked=False):
    """Every grant (active only unless ``include_revoked``), newest effective first."""
    return _base(include_revoked)


def awards_by_cycle(cycle, *, include_revoked=False):
    return _base(include_revoked).filter(cycle=cycle)


def awards_by_award_type(award_type, *, include_revoked=False):
    return _base(include_revoked).filter(award_type=award_type)


def awards_by_chapter(chapter, *, include_revoked=False):
    return _base(include_revoked).filter(Q(recipient_chapter=chapter) | Q(recipient_member__chapter=chapter))


def awards_by_region(region, *, include_revoked=False):
    return _base(include_revoked).filter(
        Q(recipient_region=region) | Q(recipient_chapter__region=region) | Q(recipient_member__chapter__region=region)
    )


def member_award_history(member, *, include_revoked=True):
    """A member's awards in chronological (effective-date) order, incl. revoked."""
    return _base(include_revoked).filter(recipient_member=member).order_by("effective_date", "id")


def chapter_award_history(chapter, *, include_revoked=True):
    """A chapter's awards (the chapter's and its members') in chronological order."""
    return (
        _base(include_revoked)
        .filter(Q(recipient_chapter=chapter) | Q(recipient_member__chapter=chapter))
        .order_by("effective_date", "id")
    )
