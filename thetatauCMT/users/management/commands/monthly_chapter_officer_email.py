import datetime
from django.core.management import BaseCommand
from django.core.mail import send_mail
from users.notifications import OfficerMonthly, RDMonthly
from chapters.models import Chapter
from regions.models import Region


# python manage.py monthly_chapter_officer_email
class Command(BaseCommand):
    # Show this when the user types help
    help = "Send monthly email to chapter officers on the first of the month"

    def add_arguments(self, parser):
        parser.add_argument("-override", action="store_true")

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
        override = options.get("override", False)
        if today == 1 or override:
            change_messages = []
            for chapter in Chapter.objects.all():
                if not chapter.active:
                    continue
                result = OfficerMonthly(chapter).send()
                change_messages.append(f"{result}: {chapter}")
            change_messages.append("<br>REGIONS<br>")
            for region in Region.objects.all():
                if region.slug == "test":
                    continue
                result = RDMonthly(region).send()
                change_messages.append(f"{result}: {region}")
            result = RDMonthly(region="colony").send()
            change_messages.append(f"{result}: colony")
            change_message = "<br>".join(change_messages)
            send_mail(
                "CMT Monthly Email Task",
                f"Email sent to chapters:<br>{change_message}",
                "cmt@thetatau.org",
                ["cmt@thetatau.org"],
                fail_silently=True,
            )
        else:
            print("Not Today")
