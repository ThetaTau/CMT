from django.conf import settings

if settings.DJANGO_EMAIL_LIVE:
    from anymail.backends.mailjet import EmailBackend
else:
    from django.core.mail.backends.console import EmailBackend
from bandit.backends.base import HijackBackendMixin
from django_middleware_global_request.middleware import get_request


class MyHijackBackend(HijackBackendMixin, EmailBackend):
    """
    This backend intercepts outgoing messages drops them to a single email
    address, using the SendgridBackend
    """

    def send_messages(self, email_messages):
        request = get_request()
        # Test is needed to trick bandit with an unapproved email
        if request is None or request.user.is_anonymous:
            email = "cmt@thetatau.org"
        else:
            email = request.user.email
        setattr(settings, "BANDIT_EMAIL", [email, "test@thetatau.org"])
        for message in email_messages:
            message.subject = f"[TEST] {message.subject}"
            try:
                message.alternatives = [
                    (
                        message.alternatives[0][0].replace(
                            '<div id="hijacked"></div>',
                            "<br>HIJACKED EMAIL! Email only send to you as a test.<br>",
                        ),
                        "text/html",
                    )
                ]
            except:
                pass
        super().send_messages(email_messages)
