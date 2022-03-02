from herald import registry
from herald.base import EmailNotification
from django.conf import settings
from django.core.files.base import ContentFile


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
        from forms.flows import render_to_pdf

        info = {"Test": "This is a test"}
        forms = render_to_pdf(
            "forms/disciplinary_form_pdf.html",
            context={"info": info},
        )

        return ["This is a test message", [ContentFile(forms, name="Testfile.pdf")]]
