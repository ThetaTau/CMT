"""Categorized email-unsubscribe registry and helpers.

Central Office sends several distinct mailings (graduation-anniversary
notes, the Velocitas newsletter, birthday greetings, and so on). Each one
should have its own opt-out so a member can silence, e.g., birthday emails
without losing the newsletter.

Registry entries are the *only* place category slugs are defined; every
sender and the unsubscribe UI reads from ``UNSUBSCRIBE_CATEGORIES``.
Adding a new mailing = append one entry here.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class UnsubscribeCategory:
    slug: str
    label: str
    description: str


# Sentinel used by the confirm view to represent the "unsubscribe from
# every optional mailing" toggle (flips ``User.unsubscribe_email``).
CATEGORY_ALL = "all"

UNSUBSCRIBE_CATEGORIES = [
    UnsubscribeCategory(
        slug="grad_anniversary",
        label="Graduation Anniversary",
        description=("Occasional greetings marking a milestone anniversary of your " "graduation from your chapter."),
    ),
    UnsubscribeCategory(
        slug="velocitas",
        label="Velocitas Newsletter",
        description="The Velocitas alumni newsletter.",
    ),
    UnsubscribeCategory(
        slug="birthday",
        label="Birthday Celebrations",
        description="Birthday greetings from Theta Tau.",
    ),
    UnsubscribeCategory(
        slug="award_digest",
        label="Awards Digest",
        description="A monthly summary of awards granted across Theta Tau.",
    ),
    UnsubscribeCategory(
        slug="chapter_founding_day",
        label="Chapter Founding Day",
        description="An annual celebration of your chapter's founding by Theta Tau.",
    ),
]

CATEGORY_SLUGS = {c.slug for c in UNSUBSCRIBE_CATEGORIES}


def get_category(slug):
    """Return the :class:`UnsubscribeCategory` for ``slug`` or ``None``."""
    for category in UNSUBSCRIBE_CATEGORIES:
        if category.slug == slug:
            return category
    return None


def _user_category_list(user):
    return list(getattr(user, "unsubscribe_categories", None) or [])


def is_unsubscribed(user, category_slug):
    """True when ``user`` should NOT receive mail in ``category_slug``.

    A user is considered unsubscribed from a category when any of:
      * ``user.no_contact`` is True
      * ``user.unsubscribe_email`` is True (global opt-out)
      * ``category_slug`` is present in ``user.unsubscribe_categories``
    """
    if getattr(user, "no_contact", False):
        return True
    if getattr(user, "unsubscribe_email", False):
        return True
    return category_slug in _user_category_list(user)


def set_category_unsubscribed(user, category_slug, unsubscribed, *, save=True):
    """Add or remove ``category_slug`` from the user's opt-out list.

    Returns True when the stored list changed. When ``save`` is True and a
    change occurred, persists ``unsubscribe_categories`` via ``update_fields``.
    """
    if category_slug not in CATEGORY_SLUGS:
        raise ValueError(f"Unknown unsubscribe category: {category_slug!r}")
    current = _user_category_list(user)
    if unsubscribed and category_slug not in current:
        current.append(category_slug)
    elif not unsubscribed and category_slug in current:
        current.remove(category_slug)
    else:
        return False
    user.unsubscribe_categories = current
    if save:
        user.save(update_fields=["unsubscribe_categories"])
    return True
