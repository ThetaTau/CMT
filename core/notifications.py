import logging

from django.conf import settings
from django.core.files.base import ContentFile
from herald import registry
from herald.base import EmailNotification

logger = logging.getLogger(__name__)

# herald joins the recipient list with commas into ``SentNotification.recipients``,
# a varchar(2000). Overflowing it raises a DataError from ``send()``, which takes
# down the whole request rather than just failing to email.
MAX_RECIPIENT_CHARS = 2000


def capped_recipients(emails, context=""):
    """Sorted, de-duplicated addresses that fit herald's recipients column.

    Use for any ``to_emails`` built from a query rather than a fixed handful of
    people: a role with duplicate or stale rows, a whole chapter, or a region
    can each produce a list long enough to break the send.
    """
    unique = {email for email in emails if email}
    kept, length = [], 0
    for email in sorted(unique):
        extra = len(email) + (1 if kept else 0)
        if length + extra > MAX_RECIPIENT_CHARS:
            logger.warning(
                "Email recipient list too long%s; sending to %s of %s addresses.",
                f" for {context}" if context else "",
                len(kept),
                len(unique),
            )
            break
        kept.append(email)
        length += extra
    return kept


@registry.register_decorator()
class GenericEmail(EmailNotification):
    render_types = ["html"]
    template_name = "generic"

    def __init__(
        self,
        emails,
        subject,
        message,
        cc=None,
        reply=None,
        attachments=None,
        addressee=None,
    ):
        self.to_emails = {email for email in emails if email}
        if cc is None:
            cc = {"central.office@thetatau.org"}
        elif isinstance(cc, str):
            cc = {cc}
        elif not cc:
            cc = {}
        if reply is None:
            reply = {"central.office@thetatau.org"}
        elif isinstance(reply, str):
            reply = {reply}
        elif not reply:
            reply = {}
        if addressee is None:
            addressee = "To Whom It May Concern"
        self.cc = list({email for email in cc})
        self.reply_to = list({email for email in reply})
        self.subject = subject
        file_names = []
        if attachments:
            for file in attachments:
                if hasattr(file, "name"):
                    file_names.append(file.name)
                elif hasattr(file, "get_filename"):
                    file_names.append(file.get_filename())
        else:
            attachments = []
        self.context = {
            "file_names": file_names,
            "host": settings.CURRENT_URL,
            "message": message,
            "addressee": addressee,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = []
        for file in attachments:
            if hasattr(file, "seek"):
                file.seek(0)
                self.attachments.append(
                    (file.name, file.read(), None),
                )
            elif hasattr(file, "get_content_type"):
                self.attachments.append(file)

    @staticmethod
    def get_demo_args():
        from thetatauCMT.forms.flows import render_to_pdf

        info = {"Test": "This is a test"}
        forms = render_to_pdf(
            "forms/disciplinary_form_pdf.html",
            context={"info": info},
        )

        return ["This is a test message", [ContentFile(forms, name="Testfile.pdf")]]
