"""Thin wrapper around the Mailjet REST API (``mailjet-rest``) for on-demand
admin lookups of the messages sent to a member.

Unlike :mod:`thetatauCMT.email_tracking.signals` (which passively records webhook
events), this module actively queries Mailjet when a National Officer opens the
member-communication page. It reuses the same Mailjet credentials Anymail sends
mail with (``settings.ANYMAIL['MAILJET_API_KEY'] / ['MAILJET_SECRET_KEY']``),
falling back to the ``MJ_APIKEY_PUBLIC`` / ``MJ_APIKEY_PRIVATE`` env vars.

Two endpoints are used (see https://dev.mailjet.com/email/reference/):

* ``message`` filtered by ``ContactAlt`` (recipient email) -> messages sent to
  that address, each with an ``ID`` and a current ``Status``.
* ``messagehistory`` by message ``ID`` -> the ordered event history for one
  message (sent, opened, clicked, ...).
"""

import logging
import os
from datetime import datetime, time, timezone

from django.conf import settings

logger = logging.getLogger(__name__)


class MailjetConfigurationError(Exception):
    """Raised when Mailjet API credentials or the client library are missing."""


class MailjetAPIError(Exception):
    """Raised when the Mailjet API returns a non-success response."""


def _credentials():
    anymail = getattr(settings, "ANYMAIL", {}) or {}
    api_key = anymail.get("MAILJET_API_KEY") or os.environ.get("MJ_APIKEY_PUBLIC")
    api_secret = anymail.get("MAILJET_SECRET_KEY") or os.environ.get("MJ_APIKEY_PRIVATE")
    return api_key, api_secret


def is_configured():
    """True when both credentials and the client library are available."""
    api_key, api_secret = _credentials()
    if not api_key or not api_secret:
        return False
    try:
        import mailjet_rest  # noqa: F401
    except ImportError:
        return False
    return True


def get_client():
    """Build an authenticated Mailjet v3 client.

    Raises :class:`MailjetConfigurationError` if the library or credentials are
    unavailable.
    """
    try:
        from mailjet_rest import Client
    except ImportError as exc:  # pragma: no cover - library is a declared dep
        raise MailjetConfigurationError("The 'mailjet-rest' package is not installed.") from exc

    api_key, api_secret = _credentials()
    if not api_key or not api_secret:
        raise MailjetConfigurationError(
            "Mailjet API credentials are not configured "
            "(settings.ANYMAIL['MAILJET_API_KEY'] / ['MAILJET_SECRET_KEY'])."
        )
    return Client(auth=(api_key, api_secret), version="v3")


def _check(result, context):
    status_code = getattr(result, "status_code", None)
    if status_code != 200:
        body = ""
        try:
            body = result.json()
        except Exception:  # pragma: no cover - defensive
            body = getattr(result, "text", "")
        raise MailjetAPIError(f"Mailjet {context} returned {status_code}: {body}")
    return result.json()


def _parse_iso(value):
    if not value:
        return None
    try:
        # Mailjet returns e.g. "2018-01-01T00:00:00" (assume UTC).
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _parse_epoch(value):
    if value in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (ValueError, OSError, TypeError):
        return None


def _to_timestamp(value, end_of_day=False):
    """Convert a ``date``/``datetime`` to a Unix timestamp (seconds, UTC)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:  # date
        dt = datetime.combine(value, time.max if end_of_day else time.min)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _apply_date_filters(filters, date_from, date_to):
    from_ts = _to_timestamp(date_from)
    to_ts = _to_timestamp(date_to, end_of_day=True)
    if from_ts is not None:
        filters["FromTS"] = from_ts
    if to_ts is not None:
        filters["ToTS"] = to_ts


def get_messages_for_email(email, limit=25, offset=0, date_from=None, date_to=None, client=None):
    """Return a page of the messages Mailjet has sent to ``email``.

    ``ShowSubject`` is requested so the ``Subject`` field comes back populated
    (Mailjet omits it otherwise). ``Limit`` / ``Offset`` paginate the result and
    ``date_from`` / ``date_to`` narrow it server-side via ``FromTS`` / ``ToTS``.

    Returns a dict ``{"data": [...], "total": int, "count": int}`` where each
    item in ``data`` is the raw Mailjet ``message`` dict augmented with a parsed
    ``arrived_at`` datetime. Newest first.
    """
    if not email:
        return {"data": [], "total": 0, "count": 0}
    client = client or get_client()
    filters = {
        "ContactAlt": email,
        "Limit": limit,
        "Offset": offset,
        "Sort": "ArrivedAt DESC",
        "ShowSubject": "true",
    }
    _apply_date_filters(filters, date_from, date_to)
    result = client.message.get(filters=filters)
    payload = _check(result, "message list")
    data = payload.get("Data", []) or []
    for item in data:
        item["arrived_at"] = _parse_iso(item.get("ArrivedAt"))
    try:
        total = int(payload.get("Total"))
    except (TypeError, ValueError):
        total = len(data)
    return {"data": data, "total": total, "count": len(data)}


def get_message_count(email, date_from=None, date_to=None, client=None):
    """Return the total number of Mailjet messages sent to ``email``.

    Uses Mailjet's ``countOnly`` global parameter so no message bodies are
    transferred — this is what makes an accurate total available for pagination
    (the ``/message`` list endpoint's ``Total`` field otherwise just echoes the
    number of rows in the current page). ``date_from`` / ``date_to`` narrow the
    count the same way as :func:`get_messages_for_email`.

    Returns ``None`` when the total can't be determined (e.g. the endpoint
    ignored ``countOnly`` and returned data instead), so callers can fall back
    to a heuristic.
    """
    if not email:
        return 0
    client = client or get_client()
    filters = {"ContactAlt": email, "countOnly": 1}
    _apply_date_filters(filters, date_from, date_to)
    result = client.message.get(filters=filters)
    payload = _check(result, "message count")
    # When countOnly is honoured, Data is empty and Count holds the grand total.
    if payload.get("Data"):
        return None
    value = payload.get("Count")
    if value is None:
        value = payload.get("Total")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_message_history(message_id, client=None):
    """Return the ordered event history for a single Mailjet message ``ID``.

    Each item is the raw Mailjet ``messagehistory`` dict augmented with a parsed
    ``event_at`` datetime.
    """
    if not message_id:
        return []
    client = client or get_client()
    result = client.messagehistory.get(id=str(message_id))
    data = _check(result, "message history").get("Data", []) or []
    for item in data:
        item["event_at"] = _parse_epoch(item.get("EventAt"))
    return data
