from django.core.management import BaseCommand
from csv import DictReader
from datetime import datetime
from tasks.models import Task, TaskDate

file_path = r"thetatauCMT/tasks/management/commands/date_data.csv"


# The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Add all new dates for all tasks outlined in date_data.csv"

    # A command must define handle()
    def handle(self, *args, **options):
        with open(file_path, "r") as csv_file:
            reader = DictReader(csv_file)
            for row in reader:
                print(row)
                task_obj = Task.objects.get(name=row["task"], owner=row["owner"])
                date = datetime.strptime(row["date"], "%m/%d")
                year = datetime.now().year
                if date.month < 7:
                    year = year + 1
                date = date.replace(year=year)
                print(task_obj, row["school_type"], date)
                task_date_obj = TaskDate(
                    task=task_obj, school_type=row["school_type"], date=date
                )
                task_date_obj.save()
