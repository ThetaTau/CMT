from django.conf import settings
from sendgrid_backend import SendgridBackend
# from django.core.mail.backends.console import EmailBackend
from bandit.backends.base import HijackBackendMixin
from django_global_request.middleware import get_request


class MyHijackBackend(HijackBackendMixin, SendgridBackend):
    """
    This backend intercepts outgoing messages drops them to a single email
    address, using the SendgridBackend
    """
    def send_messages(self, email_messages):
        request = get_request()
        setattr(settings, 'BANDIT_EMAIL', request.user.email)
        for message in email_messages:
            message.subject = f"[TEST] {message.subject}"
        super().send_messages(email_messages)
