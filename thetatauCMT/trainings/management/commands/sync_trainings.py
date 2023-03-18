from django.core.management import BaseCommand
from trainings.models import Training


# python manage.py sync_trainings
class Command(BaseCommand):
    # Show this when the user types help
    help = "Sync Trainings with LMS"

    # A command must define handle()
    def handle(self, *args, **options):
        Training.get_progress_all_users()
