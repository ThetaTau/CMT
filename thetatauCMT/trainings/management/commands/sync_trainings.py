from django.core.management import BaseCommand

from thetatauCMT.trainings.models import Training


# python manage.py sync_trainings
class Command(BaseCommand):
    # Show this when the user types help
    help = "Sync Trainings with LMS"

    # A command must define handle()
    def handle(self, *args, **options):
        Training.get_progress_all_users()
        try:
            # Also pull course progress from the new Open edX (ed.thetatau.org)
            # system. Wrapped so an Open edX outage/misconfig can't abort the
            # Vector LMS sync that ran above.
            Training.get_progress_all_users_ed()
        except Exception as exc:
            self.stderr.write(f"Open edX progress sync failed: {exc}")
