import os
from django.core.management import BaseCommand
from csv import DictReader
from users.models import User


# python manage.py badge_fixes secrets\ld_badgefix.csv -test
class Command(BaseCommand):
    # Show this when the user types help
    help = (
        "Command to fix badge numbers for members. \n"
        "First row should be: "
        "    email, correct\n"
        "Will attempt to find by email then current badge number"
    )

    def add_arguments(self, parser):
        parser.add_argument("file_path", nargs=1, type=str)
        parser.add_argument("-test", action="store_true")

    # A command must define handle()
    def handle(self, *args, **options):
        file_path = options["file_path"][0]
        if not os.path.exists(file_path):
            print(f"{file_path} does not exist")
            return
        test = options.get("test", False)
        print(f"Test mode {test}")
        with open(file_path, "r") as csv_file:
            reader = DictReader(csv_file)
            message = User.fix_badge_numbers(reader, test, sep="\n")
            print(message)
