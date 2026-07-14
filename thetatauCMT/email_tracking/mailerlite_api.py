"""Thin wrapper around the MailerLite API for admin lookups of a member's
subscriber activity.

Another part of the organization uses MailerLite (mailerlite.com) for its
mailing. This lets a National Officer see a member's MailerLite subscriber
activity (opens, clicks, sends, ...) merged into the email-communication table.

Flow (per https://developers.mailerlite.com/api/subscribers):

1. Look up the subscriber by email (``GET /api/subscribers/{email}``); a 404
   means the address is not a MailerLite subscriber.
2. If found, fetch their activity log
   (``GET /api/subscribers/{subscriber_id}/activity``).

Uses the ``MAILERLITE_API_KEY`` Django setting (read from the environment in
``config/settings/base.py``).
"""

import logging
from datetime import datetime, timezone
from urllib.parse import quote

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = "https://connect.mailerlite.com/api"
TIMEOUT = 15


class MailerLiteConfigurationError(Exception):
    """Raised when the MailerLite API key is missing."""


class MailerLiteAPIError(Exception):
    """Raised when the MailerLite API returns a non-success response."""


def _api_key():
    return getattr(settings, "MAILERLITE_API_KEY", "")


def is_configured():
    return bool(_api_key())


def _headers():
    key = _api_key()
    if not key:
        raise MailerLiteConfigurationError("MAILERLITE_API_KEY is not configured.")
    return {"Authorization": f"Bearer {key}", "Accept": "application/json"}


def parse_date(value):
    """Parse a MailerLite timestamp into an aware UTC datetime (or None)."""
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def activity_subject(entry):
    """Best-effort subject/name for a MailerLite activity-log entry.

    Real entries carry the campaign/email name under ``properties`` (e.g.
    ``properties.campaign_name``); older/other shapes are handled as fallbacks.
    """
    props = entry.get("properties")
    if isinstance(props, dict):
        subject = (
            props.get("campaign_name") or props.get("name") or props.get("subject") or props.get("automation_name")
        )
        if subject:
            return subject
    for key in ("report", "campaign", "email"):
        nested = entry.get(key)
        if isinstance(nested, dict):
            subject = nested.get("subject") or nested.get("name")
            if subject:
                return subject
    return entry.get("subject") or entry.get("name") or ""


def _check(resp, context):
    if resp.status_code // 100 != 2:
        try:
            body = resp.text[:300]
        except Exception:  # pragma: no cover - defensive
            body = ""
        raise MailerLiteAPIError(f"MailerLite {context} returned {resp.status_code}: {body}")
    try:
        return resp.json() or {}
    except ValueError as exc:
        raise MailerLiteAPIError(f"MailerLite {context} returned invalid JSON") from exc


def get_subscriber(email, session=None):
    """Return the MailerLite subscriber dict for ``email``, or None if the
    address is not a subscriber (404)."""
    if not email:
        return None
    session = session or requests
    resp = session.get(
        f"{API_BASE}/subscribers/{quote(email, safe='')}",
        headers=_headers(),
        timeout=TIMEOUT,
    )
    if resp.status_code == 404:
        return None
    return _check(resp, "subscriber lookup").get("data")


def get_subscriber_activity(subscriber_id, limit=100, session=None):
    """Return the subscriber's activity list (bounded, newest first).

    Uses MailerLite's ``GET /api/subscribers/{id}/activity-log`` endpoint. A 404
    (no activity resource for the subscriber) is treated as an empty list.
    """
    if not subscriber_id:
        return []
    session = session or requests
    resp = session.get(
        f"{API_BASE}/subscribers/{subscriber_id}/activity-log",
        headers=_headers(),
        params={"limit": limit},
        timeout=TIMEOUT,
    )
    if resp.status_code == 404:
        return []
    return _check(resp, "subscriber activity").get("data", []) or []


def get_activity_for_email(email, limit=100, session=None):
    """Return the raw MailerLite activity entries for ``email``.

    Empty list if the address is not a MailerLite subscriber.
    """
    subscriber = get_subscriber(email, session=session)
    if not subscriber:
        return []
    return get_subscriber_activity(subscriber.get("id"), limit=limit, session=session)


def upsert_subscriber(email, fields=None, status=None, groups=None, session=None):
    """Create or update a MailerLite subscriber (``POST /api/subscribers``).

    MailerLite treats this endpoint as an upsert keyed on the email address.
    Returns the subscriber ``data`` dict.
    """
    if not email:
        raise MailerLiteAPIError("upsert_subscriber requires an email address.")
    session = session or requests
    payload = {"email": email}
    if fields:
        payload["fields"] = fields
    if status:
        payload["status"] = status
    if groups:
        payload["groups"] = groups
    resp = session.post(
        f"{API_BASE}/subscribers",
        headers=_headers(),
        json=payload,
        timeout=TIMEOUT,
    )
    return _check(resp, f"upsert subscriber {email}").get("data")


def unsubscribe(email, session=None):
    """Mark an EXISTING MailerLite subscriber as unsubscribed.

    Only touches addresses that are already subscribers — it never creates a
    new record. Returns True when a subscriber was changed to ``unsubscribed``,
    False when the address is not a subscriber or was already unsubscribed.
    """
    subscriber = get_subscriber(email, session=session)
    if not subscriber:
        return False
    if subscriber.get("status") == "unsubscribed":
        return False
    upsert_subscriber(email, status="unsubscribed", session=session)
    return True


def subscribe_if_absent(email, fields=None, groups=None, session=None):
    """Add ``email`` as an active subscriber only if it is not already known.

    Never resurrects an existing (possibly unsubscribed) subscriber — if the
    address is already in MailerLite its status is left untouched. Returns
    ``"added"`` when a new active subscriber was created, ``"exists"`` when the
    address was already a subscriber.
    """
    if get_subscriber(email, session=session) is not None:
        return "exists"
    upsert_subscriber(email, fields=fields, status="active", groups=groups, session=session)
    return "added"
