from django.conf import settings
from django.template.loader import render_to_string
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
        # Test is needed to trick bandit with an unapproved email
        setattr(settings, 'BANDIT_EMAIL', [request.user.email,
                                           'test@thetatau.org'])
        for message in email_messages:
            message.subject = f"[TEST] {message.subject}"
            context = {
                'message': '',
                'previous_recipients': message.to,
                'previous_cc': message.cc,
                'previous_bcc': message.bcc
            }
            try:
                message.alternatives = [(
                    message.alternatives[0][0].replace(
                        '<div id="hijacked"></div>',
                        render_to_string("bandit/hijacked-email-log-message.txt", context)),
                    'text/html')]
            except:
                pass
        super().send_messages(email_messages)
