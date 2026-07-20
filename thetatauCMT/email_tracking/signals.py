"""Signal receivers that record Mailjet email tracking.

Three receivers, all deliberately defensive (they must never raise):

* ``handle_post_send`` — django-anymail fires ``post_send`` after each message is
  handed to Mailjet. We create a :class:`TrackedEmail` per recipient keyed on the
  Mailjet ``MessageID`` so later open/click webhooks can be correlated. NOTE:
  anymail re-raises exceptions from ``post_send`` receivers, so a failure here
  would break the actual email send — hence the broad ``try/except``.

* ``handle_tracking`` — django-anymail fires ``tracking`` from its Mailjet webhook
  endpoint (``/anymail/mailjet/tracking/``) for every delivery/engagement event.
  We append an :class:`EmailTrackingEvent` and roll the state up onto the matching
  :class:`TrackedEmail`. A raising receiver here would turn the webhook into an
  HTTP 500 and cause Mailjet to retry forever, so this is defensive too.

* ``handle_sent_notification_saved`` — django-herald saves its ``SentNotification``
  immediately after sending. We use that to link the just-created TrackedEmail
  rows back to the herald notification (herald does not expose the ESP message id,
  so we match on subject + recipient within a short time window).
"""

import logging
from datetime import timedelta

from anymail.signals import EventType, post_send, tracking
from django.conf import settings
from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from herald.models import SentNotification

from .models import EmailTrackingEvent, TrackedEmail

logger = logging.getLogger(__name__)

# How far back to look for a TrackedEmail when linking a herald SentNotification.
LINK_WINDOW_MINUTES = getattr(settings, "EMAIL_TRACKING_LINK_WINDOW_MINUTES", 10)


def _resolve_user(recipient, metadata=None):
    """Best-effort map a recipient email (or metadata) to a User instance."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    metadata = metadata or {}
    for key in ("user_id", "user_pk"):
        value = metadata.get(key)
        if value:
            user = User.objects.filter(pk=value).first()
            if user:
                return user
    if recipient:
        user = User.objects.filter(Q(email__iexact=recipient) | Q(email_school__iexact=recipient)).first()
        if user:
            return user
        try:
            from allauth.account.models import EmailAddress

            email_address = EmailAddress.objects.filter(email__iexact=recipient).select_related("user").first()
            if email_address:
                return email_address.user
        except Exception:  # pragma: no cover - allauth always present here
            pass
    return None


@receiver(post_send, dispatch_uid="email_tracking.handle_post_send")
def handle_post_send(sender, message=None, status=None, esp_name=None, **kwargs):
    """Record a TrackedEmail per recipient right after Mailjet accepts a message."""
    try:
        recipients = getattr(status, "recipients", None) or {}
        if not recipients:
            return
        subject = (getattr(message, "subject", "") or "")[:255]
        from_email = str(getattr(message, "from_email", "") or "")[:255]
        metadata = getattr(message, "metadata", None) or {}
        tags = list(getattr(message, "tags", None) or [])
        now = timezone.now()
        for email, recipient_status in recipients.items():
            message_id = getattr(recipient_status, "message_id", None)
            if not message_id:
                continue
            TrackedEmail.objects.update_or_create(
                message_id=str(message_id),
                recipient=email,
                defaults={
                    "esp": esp_name or "Mailjet",
                    "subject": subject,
                    "from_email": from_email,
                    "metadata": metadata,
                    "tags": tags,
                    "user": _resolve_user(email, metadata),
                    "sent_at": now,
                    "last_status": getattr(recipient_status, "status", "") or "",
                },
            )
    except Exception:  # never let tracking break an email send
        logger.exception("email_tracking: failed to record post_send")


def _get_or_create_tracked(message_id, recipient, esp_name, metadata, tags, timestamp):
    tracked = TrackedEmail.objects.filter(message_id=message_id, recipient=recipient).first()
    if tracked is None and recipient:
        tracked = TrackedEmail.objects.filter(message_id=message_id, recipient__iexact=recipient).first()
    if tracked is not None:
        return tracked
    # Webhook arrived without a prior post_send record (e.g. app restart, or a
    # message sent before this feature existed). Create a stub from the event.
    return TrackedEmail.objects.create(
        message_id=message_id,
        recipient=recipient or "",
        esp=esp_name or "Mailjet",
        metadata=metadata or {},
        tags=tags or [],
        user=_resolve_user(recipient, metadata),
        sent_at=timestamp or timezone.now(),
    )


def _apply_event_to_tracked(tracked, event_type, timestamp, reject_reason=None):
    fields = {"last_status", "modified"}
    tracked.last_status = event_type
    if reject_reason:
        tracked.reject_reason = reject_reason
        fields.add("reject_reason")
    if event_type == EventType.DELIVERED:
        if tracked.delivered_at is None:
            tracked.delivered_at = timestamp
            fields.add("delivered_at")
    elif event_type == EventType.OPENED:
        tracked.open_count = (tracked.open_count or 0) + 1
        tracked.last_opened_at = timestamp
        fields.update({"open_count", "last_opened_at"})
        if tracked.first_opened_at is None:
            tracked.first_opened_at = timestamp
            fields.add("first_opened_at")
    elif event_type == EventType.CLICKED:
        tracked.click_count = (tracked.click_count or 0) + 1
        tracked.last_clicked_at = timestamp
        fields.update({"click_count", "last_clicked_at"})
        if tracked.first_clicked_at is None:
            tracked.first_clicked_at = timestamp
            fields.add("first_clicked_at")
    elif event_type in (EventType.BOUNCED, EventType.REJECTED, EventType.FAILED):
        if tracked.bounced_at is None:
            tracked.bounced_at = timestamp
            fields.add("bounced_at")
    elif event_type == EventType.COMPLAINED:
        if tracked.complained_at is None:
            tracked.complained_at = timestamp
            fields.add("complained_at")
    elif event_type == EventType.UNSUBSCRIBED:
        if tracked.unsubscribed_at is None:
            tracked.unsubscribed_at = timestamp
            fields.add("unsubscribed_at")
    tracked.save(update_fields=list(fields))


@receiver(tracking, dispatch_uid="email_tracking.handle_tracking")
def handle_tracking(sender, event=None, esp_name=None, **kwargs):
    """Persist a Mailjet tracking event and roll it up onto the TrackedEmail."""
    try:
        if event is None:
            return
        message_id = getattr(event, "message_id", None)
        recipient = getattr(event, "recipient", None) or ""
        event_type = getattr(event, "event_type", "") or ""
        timestamp = getattr(event, "timestamp", None) or timezone.now()
        metadata = getattr(event, "metadata", None) or {}
        tags = list(getattr(event, "tags", None) or [])
        raw = getattr(event, "esp_event", None)
        if not isinstance(raw, (dict, list)):
            raw = {}

        tracked = None
        if message_id:
            tracked = _get_or_create_tracked(str(message_id), recipient, esp_name, metadata, tags, timestamp)

        EmailTrackingEvent.objects.create(
            tracked_email=tracked,
            esp=esp_name or "Mailjet",
            message_id=str(message_id) if message_id else "",
            recipient=recipient,
            event_type=event_type,
            timestamp=timestamp,
            click_url=getattr(event, "click_url", "") or "",
            user_agent=(getattr(event, "user_agent", "") or "")[:500],
            reject_reason=getattr(event, "reject_reason", "") or "",
            mta_response=getattr(event, "mta_response", "") or "",
            tags=tags,
            metadata=metadata,
            raw=raw,
        )

        if tracked is not None:
            _apply_event_to_tracked(
                tracked,
                event_type,
                timestamp,
                reject_reason=getattr(event, "reject_reason", None),
            )
    except Exception:  # never 500 the webhook -> avoid infinite Mailjet retries
        logger.exception("email_tracking: failed to process tracking event")


@receiver(
    post_save,
    sender=SentNotification,
    dispatch_uid="email_tracking.handle_sent_notification_saved",
)
def handle_sent_notification_saved(sender, instance, created, **kwargs):
    """Link freshly-created TrackedEmail rows back to their herald notification."""
    try:
        if instance.status != SentNotification.STATUS_SUCCESS:
            return
        recipients = [part.strip() for part in (instance.recipients or "").split(",") if part.strip()]
        if not recipients:
            return
        window_start = timezone.now() - timedelta(minutes=LINK_WINDOW_MINUTES)
        query = TrackedEmail.objects.filter(
            sent_notification__isnull=True,
            recipient__in=recipients,
            sent_at__gte=window_start,
        )
        if instance.subject:
            query = query.filter(subject=(instance.subject or "")[:255])
        for tracked in query:
            update_fields = ["sent_notification", "notification_class", "modified"]
            tracked.sent_notification = instance
            tracked.notification_class = instance.notification_class or ""
            if tracked.user_id is None and instance.user_id:
                tracked.user_id = instance.user_id
                update_fields.append("user")
            tracked.save(update_fields=update_fields)
    except Exception:
        logger.exception(
            "email_tracking: failed to link SentNotification %s",
            getattr(instance, "pk", None),
        )
