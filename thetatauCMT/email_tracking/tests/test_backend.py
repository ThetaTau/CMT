from django.core.mail import EmailMessage
from django.test import override_settings

from core.email import TrackingEmailBackendMixin


class _Recorder:
    """Minimal stand-in for a real email backend that records sent messages."""

    def __init__(self, *args, **kwargs):
        self.sent = []

    def send_messages(self, email_messages):
        self.sent = list(email_messages or [])
        return len(self.sent)


class _TrackingBackend(TrackingEmailBackendMixin, _Recorder):
    pass


def _message():
    return EmailMessage(subject="Hi", body="body", from_email="cmt@thetatau.org", to=["c@d.com"])


def test_backend_enables_open_and_click_tracking():
    backend = _TrackingBackend()
    msg = _message()
    backend.send_messages([msg])
    assert msg.track_opens is True
    assert msg.track_clicks is True
    assert backend.sent == [msg]


@override_settings(EMAIL_TRACK_OPENS=False, EMAIL_TRACK_CLICKS=False)
def test_backend_respects_disable_settings():
    backend = _TrackingBackend()
    msg = _message()
    backend.send_messages([msg])
    assert msg.track_opens is False
    assert msg.track_clicks is False


def test_backend_does_not_override_explicit_message_setting():
    backend = _TrackingBackend()
    msg = _message()
    msg.track_opens = False  # caller opted a specific message out
    backend.send_messages([msg])
    assert msg.track_opens is False  # respected
    assert msg.track_clicks is True  # default still applied
