from django.core.management import BaseCommand
from trainings.models import Training


# python manage.py sync_trainings
class Command(BaseCommand):
    # Show this when the user types help
    help = "Sync Trainings with LMS"

    def add_arguments(self, parser):
        # python manage.py init_shingle_task -override
        parser.add_argument("-override", action="store_true")
        parser.add_argument(
            "-days", nargs=1, type=int, help="Number of days to process"
        )

    # A command must define handle()
    def handle(self, *args, **options):
        override = options.get("override", False)
        days = int(options.get("days", [7])[0])
        Training.get_progress_all_users(override=override, days=days)
