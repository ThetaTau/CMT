import datetime
from django.core.management import BaseCommand
from viewflow.models import Task
from viewflow.activation import STATUS
from forms.flows import DisciplinaryProcessFlow


class Command(BaseCommand):
    # Show this when the user types help
    help = "Check discipline process, if today + 1 process function tasks"

    def add_arguments(self, parser):
        parser.add_argument("-date", nargs=1, type=str, help="all tasks < date + 1 day")
        parser.add_argument(
            "-chapter", nargs=1, type=str, help="Only process for this chapter"
        )

    # A command must define handle()
    def handle(self, *args, **options):
        date_str = options.get("date", None)
        chapter_only = options.get("chapter", None)
        date = datetime.datetime.today()
        if date_str:
            date_str = date_str[0]
            date = datetime.datetime.strptime(date_str, "%Y%m%d")
        date += datetime.timedelta(days=1)
        print(f"Process tasks for date <= {date}")
        query = dict(
            process__flow_class=DisciplinaryProcessFlow,
            flow_task_type="FUNC",
            status=STATUS.NEW,
            process__disciplinaryprocess__trial_date__lte=date,
        )
        if chapter_only is not None:
            chapter_only = chapter_only[0]
            print(f"Only for chapter {chapter_only}")
            query.update({"process__disciplinaryprocess__chapter__name": chapter_only})
        function_tasks = Task.objects.filter(**query)
        print(f"Tasks found {function_tasks.count()}")
        for function_task in function_tasks.all():
            # This could be run by function_task.flow_task.run(function_task)
            # But I want to be more specific and direct just to be sure...
            if function_task.flow_task.name == "delay":
                print("Email regent task")
                func = DisciplinaryProcessFlow.start_email_regent
            else:  # function_task.flow_task.name == "delay_ec"
                print("Send to EC task")
                func = DisciplinaryProcessFlow.start_send_ec
            func(function_task.process.pk)
