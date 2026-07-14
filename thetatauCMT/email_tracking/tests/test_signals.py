import pytest
from anymail.message import AnymailRecipientStatus, AnymailStatus
from anymail.signals import AnymailTrackingEvent, EventType, post_send, tracking
from django.utils import timezone
from herald.models import SentNotification

from thetatauCMT.email_tracking.models import EmailTrackingEvent, TrackedEmail
from thetatauCMT.users.tests.factories import UserFactory


class _FakeMessage:
    """Stand-in for the EmailMessage anymail passes to the post_send signal."""

    def __init__(self, subject, from_email="cmt@thetatau.org", metadata=None, tags=None):
        self.subject = subject
        self.from_email = from_email
        self.metadata = metadata or {}
        self.tags = tags or []


def _status(message_id, email, status="sent"):
    anymail_status = AnymailStatus()
    anymail_status.set_recipient_status({email: AnymailRecipientStatus(message_id=message_id, status=status)})
    return anymail_status


def _send_post_send(message_id, email, subject="Subject", metadata=None):
    msg = _FakeMessage(subject, metadata=metadata)
    post_send.send(
        sender=None,
        message=msg,
        status=_status(message_id, email),
        esp_name="Mailjet",
    )


def _send_tracking(event_type, message_id, email, **kwargs):
    kwargs.setdefault("timestamp", timezone.now())
    event = AnymailTrackingEvent(event_type=event_type, message_id=message_id, recipient=email, **kwargs)
    tracking.send(sender=None, event=event, esp_name="Mailjet")
    return event


@pytest.mark.django_db
def test_post_send_creates_tracked_email():
    _send_post_send("1001", "a@b.com", subject="Welcome")
    tracked = TrackedEmail.objects.get(message_id="1001", recipient="a@b.com")
    assert tracked.subject == "Welcome"
    assert tracked.last_status == "sent"
    assert tracked.esp == "Mailjet"


@pytest.mark.django_db
def test_post_send_resolves_user_by_email():
    user = UserFactory.create(email="member@example.com")
    _send_post_send("1002", "member@example.com")
    tracked = TrackedEmail.objects.get(message_id="1002")
    assert tracked.user_id == user.pk


@pytest.mark.django_db
def test_post_send_resolves_user_from_metadata_user_id():
    user = UserFactory.create()
    _send_post_send("1003", "someone-else@example.com", metadata={"user_id": user.pk})
    tracked = TrackedEmail.objects.get(message_id="1003")
    assert tracked.user_id == user.pk


@pytest.mark.django_db
def test_tracking_open_updates_counts_and_logs_event():
    TrackedEmail.objects.create(message_id="2001", recipient="a@b.com", subject="S")
    _send_tracking(EventType.OPENED, "2001", "a@b.com", user_agent="Mozilla/5.0")
    tracked = TrackedEmail.objects.get(message_id="2001")
    assert tracked.open_count == 1
    assert tracked.first_opened_at is not None
    assert tracked.last_opened_at is not None
    assert tracked.opened is True
    assert tracked.last_status == EventType.OPENED
    event = EmailTrackingEvent.objects.get(message_id="2001", event_type=EventType.OPENED)
    assert event.tracked_email_id == tracked.pk
    assert event.user_agent == "Mozilla/5.0"


@pytest.mark.django_db
def test_tracking_open_twice_increments_open_count():
    TrackedEmail.objects.create(message_id="2005", recipient="a@b.com")
    _send_tracking(EventType.OPENED, "2005", "a@b.com")
    _send_tracking(EventType.OPENED, "2005", "a@b.com")
    tracked = TrackedEmail.objects.get(message_id="2005")
    assert tracked.open_count == 2
    assert EmailTrackingEvent.objects.filter(message_id="2005").count() == 2


@pytest.mark.django_db
def test_tracking_creates_stub_when_no_prior_record():
    _send_tracking(EventType.OPENED, "2002", "x@y.com")
    assert TrackedEmail.objects.filter(message_id="2002", recipient="x@y.com").exists()


@pytest.mark.django_db
def test_tracking_click_and_bounce_set_state():
    TrackedEmail.objects.create(message_id="2003", recipient="a@b.com")
    _send_tracking(EventType.CLICKED, "2003", "a@b.com", click_url="https://example.org")
    _send_tracking(EventType.BOUNCED, "2003", "a@b.com", reject_reason="bounced")
    tracked = TrackedEmail.objects.get(message_id="2003")
    assert tracked.click_count == 1
    assert tracked.first_clicked_at is not None
    assert tracked.clicked is True
    assert tracked.bounced_at is not None
    assert tracked.reject_reason == "bounced"


@pytest.mark.django_db
def test_herald_sent_notification_links_tracked_email():
    TrackedEmail.objects.create(
        message_id="3001",
        recipient="a@b.com",
        subject="Herald Subject",
        sent_at=timezone.now(),
    )
    sent_notification = SentNotification.objects.create(
        recipients="a@b.com",
        subject="Herald Subject",
        date_sent=timezone.now(),
        status=SentNotification.STATUS_SUCCESS,
        notification_class="core.notifications.GenericEmail",
    )
    tracked = TrackedEmail.objects.get(message_id="3001")
    assert tracked.sent_notification_id == sent_notification.pk
    assert tracked.notification_class == "core.notifications.GenericEmail"


@pytest.mark.django_db
def test_herald_link_ignores_failed_notifications():
    TrackedEmail.objects.create(
        message_id="3002",
        recipient="a@b.com",
        subject="Failed Subject",
        sent_at=timezone.now(),
    )
    SentNotification.objects.create(
        recipients="a@b.com",
        subject="Failed Subject",
        date_sent=timezone.now(),
        status=SentNotification.STATUS_FAILED,
        notification_class="core.notifications.GenericEmail",
    )
    tracked = TrackedEmail.objects.get(message_id="3002")
    assert tracked.sent_notification_id is None


@pytest.mark.django_db
def test_full_flow_send_then_open_links_user_and_records_open():
    user = UserFactory.create(email="flow@example.com")
    _send_post_send("4001", "flow@example.com", subject="Flow")
    _send_tracking(EventType.DELIVERED, "4001", "flow@example.com")
    _send_tracking(EventType.OPENED, "4001", "flow@example.com")
    tracked = TrackedEmail.objects.get(message_id="4001")
    assert tracked.user_id == user.pk
    assert tracked.delivered_at is not None
    assert tracked.open_count == 1
    assert EmailTrackingEvent.objects.filter(message_id="4001").count() == 2
