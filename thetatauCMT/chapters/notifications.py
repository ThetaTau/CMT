from herald import registry
from herald.base import EmailNotification
from django.conf import settings
from core.models import current_term


@registry.register_decorator()
class DuesReminder(EmailNotification):
    render_types = ["html"]
    template_name = "dues_reminder"
    subject = "Chapter Dues Test Roster"

    def __init__(self, chapter, attachment):
        officer_list, previous = chapter.get_current_officers_council(False)
        # set list of emails to send to
        emails = set([officer.email for officer in officer_list]) | set(
            chapter.get_generic_chapter_emails()
        )
        emails = {email for email in emails if email}
        self.to_emails = emails
        self.cc = ["accounting@thetatau.org"]
        self.reply_to = ["accounting@thetatau.org"]
        if not chapter.candidate_chapter:
            chapter_name = chapter.name + " Chapter"
        else:
            chapter_name = chapter.name
        self.subject = f"{chapter_name} Dues Test Roster"
        invoice_date, change_date = {
            "fa": ("October 15", "October 13"),
            "sp": ("February 28", "February 26"),
        }[current_term()]
        self.context = {
            "previous_officers": previous,
            "chapter": chapter_name,
            "invoice_date": invoice_date,
            "change_date": change_date,
            "host": settings.CURRENT_URL,
        }
        # https://github.com/worthwhile/django-herald#email-attachments
        self.attachments = [attachment]

    @staticmethod
    def get_demo_args():  # define a static method to return list of args needed to initialize class for testing
        from .models import Chapter

        test_chapter = Chapter.objects.order_by("?")[0]
        attachment = test_chapter.generate_dues_attachment()
        return [test_chapter, attachment]
