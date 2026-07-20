"""Sync Theta Tau members to/from the other organization's MailerLite list.

Two directions, both best-effort and gated on ``MAILERLITE_API_KEY``:

* :func:`unsubscribe_user` \u2014 when a member opts out of email in this system we
  unsubscribe every one of their addresses that is a MailerLite subscriber, so
  the two systems stay in agreement. It never creates a MailerLite record.
* :func:`send_users` \u2014 a National Officer bulk action that adds selected members
  to MailerLite, skipping anyone who is already a subscriber (so an existing,
  possibly-unsubscribed subscriber is never resurrected).

Every MailerLite call is wrapped so a network/API failure can never break the
member-facing save or the admin action; failures are logged and counted.
"""

import logging

import requests

from . import mailerlite_api
from .mailerlite_api import MailerLiteAPIError, MailerLiteConfigurationError

logger = logging.getLogger(__name__)

_SYNC_ERRORS = (MailerLiteConfigurationError, MailerLiteAPIError, requests.RequestException)


def _user_emails(user):
    """Return the user's distinct, non-blank email addresses (primary first)."""
    emails = []
    seen = set()
    for attr in ("email", "email_school"):
        value = (getattr(user, attr, "") or "").strip()
        if value and value.lower() not in seen:
            emails.append(value)
            seen.add(value.lower())
    return emails


def _primary_email(user):
    for attr in ("email", "email_school"):
        value = (getattr(user, attr, "") or "").strip()
        if value:
            return value
    return ""


def _subscriber_fields(user):
    fields = {}
    name = (getattr(user, "first_name", "") or getattr(user, "name", "") or "").strip()
    if name:
        fields["name"] = name
    last_name = (getattr(user, "last_name", "") or "").strip()
    if last_name:
        fields["last_name"] = last_name
    return fields


def unsubscribe_user(user, session=None):
    """Unsubscribe every one of ``user``'s addresses in MailerLite.

    Returns the number of MailerLite subscribers that were actually changed to
    ``unsubscribed``. A no-op returning 0 when MailerLite is not configured.
    """
    if not mailerlite_api.is_configured():
        return 0
    changed = 0
    for email in _user_emails(user):
        try:
            if mailerlite_api.unsubscribe(email, session=session):
                changed += 1
        except _SYNC_ERRORS as exc:
            logger.warning("MailerLite unsubscribe failed for %s: %s", email, exc)
    return changed


def send_user(user, session=None):
    """Add one member to MailerLite if not already a subscriber.

    Returns ``"added"``, ``"exists"`` or ``"skipped"`` (no email address).
    """
    email = _primary_email(user)
    if not email:
        return "skipped"
    return mailerlite_api.subscribe_if_absent(email, fields=_subscriber_fields(user), session=session)


def send_users(users, session=None):
    """Send an iterable of members to MailerLite.

    Returns a summary dict with counts for ``added``/``exists``/``skipped``/
    ``errors``. Callers should check :func:`mailerlite_api.is_configured` first
    and show the user a clear notice when it is not.
    """
    summary = {"added": 0, "exists": 0, "skipped": 0, "errors": 0}
    for user in users:
        try:
            outcome = send_user(user, session=session)
        except _SYNC_ERRORS as exc:
            logger.warning("MailerLite send failed for user %s: %s", getattr(user, "pk", "?"), exc)
            summary["errors"] += 1
            continue
        summary[outcome] += 1
    return summary
