"""Tokenized, expiring consent links unique to each nomination.

The token is the nomination's unguessable ``consent_token`` (a UUID4); an
expiry timestamp (``consent_token_expires``) makes it time-limited. Issuing a
token rotates the UUID and sets a fresh expiry so any previously mailed link is
invalidated.
"""

import datetime
import uuid

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from .models import Nomination

# How long a consent link stays valid after it is issued.
CONSENT_TOKEN_MAX_AGE_DAYS = getattr(settings, "NOMINATION_CONSENT_TOKEN_MAX_AGE_DAYS", 30)


def issue_consent_token(nomination):
    """Rotate the nomination's consent token and set a fresh expiry.

    Returns the new token. Any link mailed with the previous token stops
    working.
    """
    nomination.consent_token = uuid.uuid4()
    nomination.consent_token_expires = timezone.now() + datetime.timedelta(days=CONSENT_TOKEN_MAX_AGE_DAYS)
    nomination.save(update_fields=["consent_token", "consent_token_expires"])
    return nomination.consent_token


def consent_link(nomination):
    """Absolute URL to the tokenized (no-login) consent landing page."""
    host = (getattr(settings, "CURRENT_URL", "") or "").rstrip("/")
    path = reverse("nominations:consent", kwargs={"token": nomination.consent_token})
    return f"{host}{path}"


def get_nomination_by_token(token):
    """Return the :class:`Nomination` for ``token``, or ``None`` if unknown.

    ``token`` may be a ``uuid.UUID`` or a string; a malformed value yields
    ``None`` rather than raising.
    """
    if not token:
        return None
    try:
        token = uuid.UUID(str(token))
    except (ValueError, AttributeError, TypeError):
        return None
    return Nomination.objects.filter(consent_token=token).first()
