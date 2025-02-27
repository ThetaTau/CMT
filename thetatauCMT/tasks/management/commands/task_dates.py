from django.core.management import BaseCommand
from django.db import IntegrityError
from csv import DictReader
from datetime import datetime
from tasks.models import Task, TaskDate

file_path = r"thetatauCMT/tasks/management/commands/date_data.csv"

# The class must be named Command, and subclass BaseCommand
class Command(BaseCommand):
    # Show this when the user types help
    help = "Add all dates for next academic year for all tasks outlined in date_data.csv "

    def add_arguments(self, parser):
        parser.add_argument("--current-year", action="store_true", help="Use dates for the CURRENT academic year")

    # A command must define handle()
    def handle(self, *args, **options):
        base_year = self._target_academic_year(options["current_year"])
        print(f"Adding tasks for the {base_year}-{base_year + 1} academic year")

        with open(file_path, "r") as csv_file:
            reader = DictReader(csv_file)
            for row in reader:
                print(row)
                task_obj = Task.objects.get(name=row["task"], owner=row["owner"])
                date = datetime.strptime(row["date"], "%m/%d")
                year = base_year
                if self._is_spring_month(date.month):
                    year += 1
                date = date.replace(year=year)
                print("    ", task_obj, row["school_type"], date)
                try:
                    task_date_obj = TaskDate(
                        task=task_obj, school_type=row["school_type"], date=date
                    )
                    task_date_obj.save()
                except IntegrityError:
                    print(f"    Task {task_obj} date already exists {date}")
    
    def _target_academic_year(self, use_current_year):
        target_year = datetime.now().year
        use_next_year = not use_current_year
        is_currently_spring = self._is_spring_month(datetime.now().month)
        is_currently_fall = not is_currently_spring

        if use_current_year and is_currently_spring: target_year -= 1
        elif use_next_year and is_currently_fall: target_year += 1

        return target_year
    
    def _is_spring_month(self, month):
        return month < 7
