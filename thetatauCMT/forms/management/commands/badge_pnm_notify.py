"""
Notes:
    To test run command
        docker-compose -f local.yml run --rm django python manage.py badge_pnm_notify
"""

# Includes
import datetime

from django.core.management import BaseCommand
from herald.models import SentNotification

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.forms.notifications import BadgePNMNotify


class Command(BaseCommand):
    # Show this when the user types help
    help = "Send email to PNM with information about the badges"

    def add_arguments(self, parser):
        parser.add_argument("-chapter", nargs="+", type=str)

    # A command must define handle()
    def handle(self, *args, **options):
        self.stdout.write("Starting badge notify")
        today = datetime.date.today()
        chapters_only = options.get("chapter", None)
        if chapters_only is not None:
            chapters = Chapter.objects.filter(slug__in=chapters_only)
        else:
            chapters = Chapter.objects.exclude(active=False)
        for chapter in chapters:
            if not chapter.active or chapter.candidate_chapter:
                continue
            pledges = chapter.members.filter(
                status__status="pnm",
                status__start__lte=today - datetime.timedelta(weeks=4),
                status__end__gte=today,
            ).distinct()
            self.stdout.write(f"Found {pledges.count()} for {chapter}")
            for pledge in pledges:
                already_notified = SentNotification.objects.filter(
                    notification_class="forms.notifications.BadgePNMNotify",
                    recipients__icontains=pledge.email,
                )
                if not already_notified:
                    self.stdout.write(f"Send badge info to {chapter} {pledge}")
                    BadgePNMNotify(pledge).send()
        self.stdout.write("Finish badge notify")
