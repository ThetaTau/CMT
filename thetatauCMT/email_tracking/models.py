"""Models that persist Mailjet delivery/engagement tracking for every email.

These records are populated from django-anymail's ``post_send`` and ``tracking``
signals (see :mod:`thetatauCMT.email_tracking.signals`). They intentionally do
NOT implement any custom open-pixel tracking — opens/clicks come from Mailjet's
own tracking, surfaced through Anymail's normalized webhook events.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class TrackedEmail(models.Model):
    """One outbound message to one recipient, with aggregated tracking state.

    The primary correlation key is the ESP ``message_id`` (Mailjet's
    ``MessageID``) plus the recipient address. A row is created when a message is
    sent (``post_send``) and updated as Mailjet reports delivery, opens, clicks,
    bounces, etc. When the email originated from a django-herald notification the
    row is linked back to the herald ``SentNotification`` (which stores the full
    rendered content).
    """

    esp = models.CharField(max_length=50, default="Mailjet")
    message_id = models.CharField(max_length=255, db_index=True)
    recipient = models.CharField(max_length=254, db_index=True)
    subject = models.CharField(max_length=255, blank=True, default="")
    from_email = models.CharField(max_length=255, blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tracked_emails",
        help_text="Resolved recipient member, when the address maps to a user.",
    )
    sent_notification = models.ForeignKey(
        "herald.SentNotification",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tracked_emails",
        help_text="The django-herald notification this message came from, if any.",
    )
    notification_class = models.CharField(max_length=255, blank=True, default="")

    # Lifecycle timestamps / counters, driven by Mailjet events.
    sent_at = models.DateTimeField(default=timezone.now)
    last_status = models.CharField(max_length=30, blank=True, default="")
    delivered_at = models.DateTimeField(null=True, blank=True)
    first_opened_at = models.DateTimeField(null=True, blank=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)
    open_count = models.PositiveIntegerField(default=0)
    first_clicked_at = models.DateTimeField(null=True, blank=True)
    last_clicked_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    bounced_at = models.DateTimeField(null=True, blank=True)
    complained_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    reject_reason = models.CharField(max_length=50, blank=True, default="")

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tracked email"
        verbose_name_plural = "Tracked emails"
        unique_together = ("message_id", "recipient")
        ordering = ("-sent_at",)
        indexes = [
            models.Index(fields=["recipient", "-sent_at"]),
            models.Index(fields=["message_id"]),
        ]

    def __str__(self):
        return f"{self.subject or '(no subject)'} -> {self.recipient} [{self.last_status or 'sent'}]"

    @property
    def opened(self):
        return self.open_count > 0

    @property
    def clicked(self):
        return self.click_count > 0


class EmailTrackingEvent(models.Model):
    """Append-only log of a single Mailjet tracking event (open, click, ...)."""

    tracked_email = models.ForeignKey(
        TrackedEmail,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    esp = models.CharField(max_length=50, default="Mailjet")
    message_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    recipient = models.CharField(max_length=254, blank=True, default="", db_index=True)
    event_type = models.CharField(max_length=30, db_index=True)
    timestamp = models.DateTimeField(null=True, blank=True)
    click_url = models.TextField(blank=True, default="")
    user_agent = models.CharField(max_length=500, blank=True, default="")
    reject_reason = models.CharField(max_length=50, blank=True, default="")
    mta_response = models.TextField(blank=True, default="")
    tags = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    raw = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email tracking event"
        verbose_name_plural = "Email tracking events"
        ordering = ("-timestamp", "-created")
        indexes = [
            models.Index(fields=["message_id", "event_type"]),
            models.Index(fields=["event_type", "-created"]),
        ]

    def __str__(self):
        return f"{self.event_type} {self.recipient} @ {self.timestamp or self.created}"
