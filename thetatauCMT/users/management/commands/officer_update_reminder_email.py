"""
Notes:
    To test run command
        docker-compose -f local.yml run --rm django python manage.py officer_update_reminder_email
"""

# Includes
from django.core.management import BaseCommand

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.users.notifications import OfficerUpdateReminder


class Command(BaseCommand):
    # Show this when the user types help
    help = "Send email to eboard positions to remind to update"

    def add_arguments(self, parser):
        parser.add_argument("-override", action="store_true")
        parser.add_argument("-chapter", nargs="+", type=str)
        parser.add_argument("-rdonly", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        chapters_only = options.get("chapter", None)
        if chapters_only is not None:
            chapters = Chapter.objects.filter(slug__in=chapters_only)
        else:
            chapters = Chapter.objects.exclude(active=False)
        for chapter in chapters:
            if not chapter.active:
                continue
            self.stdout.write(str(chapter))
            emails, officers_to_update = chapter.get_about_expired_coucil()
            if officers_to_update and emails:
                # Only send the daily reminder when there is at least one chapter
                # recipient. Previously an unresponsive chapter with no current or
                # past officers still sent a daily email whose only recipient was
                # the cc'd Regional Director; the RD now gets a weekly digest
                # instead (region_officer_reminder_digest).
                self.stdout.write(f"Sending message to: {chapter}\n")
                result = OfficerUpdateReminder(chapter, emails, officers_to_update).send()
                self.stdout.write(f"    {result}")
            elif officers_to_update:
                self.stdout.write(
                    f"{chapter} needs updates but has no chapter recipients; deferring to the weekly RD digest\n"
                )
            else:
                self.stdout.write(f"{chapter} does not need to update CMT\n")
