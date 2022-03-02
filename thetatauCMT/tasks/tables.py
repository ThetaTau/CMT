import django_tables2 as tables
from django_tables2.utils import A
from .models import TaskDate


class TaskTable(tables.Table):
    task_name = tables.LinkColumn(
        "tasks:complete", accessor="task.name", args=[A("pk")]
    )
    form = tables.URLColumn(
        verbose_name="Form to Submit",
        accessor="task.resource",
    )
    date = tables.DateColumn(verbose_name="Due Date")

    class Meta:
        model = TaskDate
        fields = (
            "task_name",
            "form",
            "date",
            "task.owner",
            "task.description",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no tasks matching the search criteria..."

    def __init__(self, complete=True, *args, **kwargs):
        extra_columns = []
        if complete:
            extra_columns.extend(
                [
                    (
                        "complete_result",
                        tables.LinkColumn(
                            "tasks:detail",
                            args=[A("complete_link")],
                            verbose_name="Complete",
                            empty_values=(),
                        ),
                    ),
                ]
            )
        kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)

    def render_form(self, record):
        task = record.task
        value = task.render_task_link
        return value
