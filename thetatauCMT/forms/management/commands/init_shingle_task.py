import datetime
from django.core.management import BaseCommand
from viewflow.models import Task
from viewflow.activation import STATUS
from forms.flows import InitiationProcessFlow


class Command(BaseCommand):
    # Show this when the user types help
    help = "Check initiation process, monthly send shingle orders"

    def add_arguments(self, parser):
        # python manage.py init_shingle_task -override
        parser.add_argument("-override", action="store_true")
        parser.add_argument(
            "-chapter", nargs=1, type=str, help="Only process for this chapter"
        )

    # A command must define handle()
    def handle(self, *args, **options):
        override = options.get("override", False)
        chapter_only = options.get("chapter", None)
        today = datetime.date.today().day
        if today == 1 or override:
            query = dict(
                process__flow_class=InitiationProcessFlow,
                flow_task_type="FUNC",
                status=STATUS.NEW,
            )
            if chapter_only is not None:
                chapter_only = chapter_only[0]
                print(f"Only for chapter {chapter_only}")
                query.update(
                    {"process__initiationprocess__chapter__name": chapter_only}
                )
            function_tasks = Task.objects.filter(**query)
            print(f"Tasks found {function_tasks.count()}")
            processes = []
            for function_task in function_tasks.all():
                if function_task.flow_task and (
                    function_task.flow_task.name == "shingle_order_delay"
                ):
                    print("Send shingle order")
                    processes.append(function_task.process)
            InitiationProcessFlow.shingle_orders(processes)
