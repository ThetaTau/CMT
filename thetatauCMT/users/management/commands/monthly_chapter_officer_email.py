import datetime
from django.core.management import BaseCommand
from django.core.mail import send_mail
from users.notifications import OfficerMonthly
from chapters.models import Chapter


class Command(BaseCommand):
    # Show this when the user types help
    help = "Send monthly email to chapter officers on the first of the month"

    # A command must define handle()
    def handle(self, *args, **options):
        """
        Pythonanywhere does not support use of celery.
        Best way to trigger is to use daily scheduled task from Pythonanywhere
        and check if the day is first of month.
        :param args:
        :param options:
        :return:
        """
        today = datetime.date.today().day
        if today == 1:
            change_messages = []
            for chapter in Chapter.objects.all():
                if not chapter.active:
                    continue
                result = OfficerMonthly(chapter).send()
                change_messages.append(f"{result}: {chapter}")
            change_message = "\n".join(change_messages)
            send_mail(
                "CMT Monthly Email Task",
                f"Email sent to chapters:\n{change_message}",
                "cmt@thetatau.org",
                ["cmt@thetatau.org"],
                fail_silently=True,
            )
        else:
            print("Not Today")
