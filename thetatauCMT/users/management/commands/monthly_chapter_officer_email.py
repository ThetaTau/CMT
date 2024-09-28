import datetime
from django.core.management import BaseCommand
from django.core.mail import send_mail
from users.notifications import OfficerMonthly, RDMonthly
from core.notifications import GenericEmail
from chapters.models import Chapter
from regions.models import Region


# python manage.py monthly_chapter_officer_email
class Command(BaseCommand):
    # Show this when the user types help
    help = "Send monthly email to chapter officers on the first of the month"

    def add_arguments(self, parser):
        parser.add_argument("-override", action="store_true")
        parser.add_argument("-chapter", nargs="+", type=str)
        parser.add_argument("-rdonly", action="store_true")

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
        month = datetime.date.today().month
        override = options.get("override", False)
        chapters_only = options.get("chapter", None)
        rdonly = options.get("rdonly", False)
        if today == 1 or override:
            change_messages = []
            if rdonly:
                chapters = []
            elif chapters_only is not None:
                chapters = Chapter.objects.filter(slug__in=chapters_only)
            else:
                chapters = Chapter.objects.exclude(active=False)
            for chapter in chapters:
                if not chapter.active:
                    continue
                print(f"Sending message to: {chapter}")
                result = OfficerMonthly(chapter).send()
                change_messages.append(f"{result}: {chapter}")
                if month in [1, 2, 3, 4, 10, 11, 12]:
                    # Avoiding the summer months
                    actives = chapter.actives().count()
                    if actives <= 30:
                        print(f"    Chapter has under 30 members: {actives} actives")
                        GenericEmail(
                            emails={
                                "council@thetatau.org",
                                "executive.director@thetatau.org",
                            },
                            subject=f"[CMT] Low Chapter Roster {chapter}",
                            message=f"ATTENTION: {chapter.full_name} at {chapter.school} has "
                            f"{actives} active members on their roster.",
                            cc={
                                "nom@thetatau.org",
                                chapter.region.email,
                                "central.office@thetatau.org",
                                "dcs@thetatau.org",
                            },
                            addressee="Dear National Officers",
                        ).send()
            if chapters_only is None or rdonly:
                change_messages.append("<br>REGIONS<br>")
                for region in Region.objects.all():
                    if region.slug == "test":
                        continue
                    print(f"Sending message to: {region}")
                    result = RDMonthly(region).send()
                    change_messages.append(f"{result}: {region}")
                result = RDMonthly(region="candidate_chapter").send()
                change_messages.append(f"{result}: candidate chapter")
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
