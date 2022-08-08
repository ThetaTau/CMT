"""
Notes:
    To test run command
        docker-compose -f local.yml run --rm django python manage.py chapter_pledges_check
"""
import datetime
from django.utils.timezone import make_aware
from django.core.management import BaseCommand
from herald.models import SentNotification
from core.models import TODAY_END
from core.notifications import GenericEmail
from chapters.models import Chapter


class Command(BaseCommand):
    # Show this when the user types help
    help = "Send email to eboard positions to remind to update"

    def add_arguments(self, parser):
        parser.add_argument("-override", action="store_true")
        parser.add_argument("-chapter", nargs="+", type=str)

    # A command must define handle()
    def handle(self, *args, **options):
        chapters_only = options.get("chapter", None)
        today = datetime.date.today().strftime("%A")
        override = options.get("override", False)
        if today != "Monday" and not override:
            print(f"Not today {today}")
            return
        if chapters_only is not None:
            chapters = Chapter.objects.filter(slug__in=chapters_only)
        else:
            chapters = Chapter.objects.exclude(active=False)
        for chapter in chapters:
            if not chapter.active:
                continue
            print(chapter)
            pledges = chapter.pledges_with_no_init_last_x_months()
            message = ""
            subject = "CMT "
            if pledges:
                # notify weekly chapter, RD, CO
                message += (
                    f"We noticed that these PNMs have not been "
                    f"initiated after 6 months:<br>"
                    f"{', '.join(pledges.values_list('name', flat=True))}.<br>"
                    f"Please complete the initiation form as soon as possible."
                )
                subject += "Pledge"
            if not chapter.pledges_last_x_months():
                # Once a semester? chapter, RD, CO
                print("    No pledges last 8 months")
                already_notified_pledges = SentNotification.objects.filter(
                    notification_class="core.notifications.GenericEmail",
                    html_content__icontains="potential new members in the last 8 months",
                    date_sent__gte=make_aware(TODAY_END - datetime.timedelta(30 * 3)),
                )
                if not already_notified_pledges:
                    if "Pledge" in subject:
                        subject += " and "
                        message += "<br><br>"
                    subject += "Initiation"
                    message += (
                        "We noticed there have been no reported "
                        "potential new members in the last 8 months. "
                        "Please make sure that your PNMs complete the "
                        "pledge form as soon as possible."
                    )

                else:
                    print("    Already notified")
            subject += " Reminder"
            if message:
                print(f"    Sending message to: {chapter}\n")
                officer_list, _ = chapter.get_current_officers_council()
                # set list of emails to send to
                emails = set([officer.email for officer in officer_list]) | set(
                    chapter.get_generic_chapter_emails()
                )
                if not chapter.candidate_chapter:
                    chapter_name = chapter.name + " Chapter"
                    region_email = chapter.region.email
                else:
                    chapter_name = chapter.name
                    region_email = "ccd@thetatau.org"
                cc = [region_email, "central.office@thetatau.org"]
                result = GenericEmail(
                    emails=emails,
                    subject=subject,
                    message=message,
                    cc=cc,
                    addressee=f"{chapter_name} officers",
                ).send()
                print("    ", result)
            else:
                print(f"    {chapter} does not need to update CMT\n")
