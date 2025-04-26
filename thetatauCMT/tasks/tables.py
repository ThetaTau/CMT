from django.utils.safestring import mark_safe
from django.urls import reverse
import django_tables2 as tables
from django_tables2.utils import A
from .models import TaskDate


class TaskTable(tables.Table):
    task_name = tables.LinkColumn(
        "tasks:complete", accessor="task__name", args=[A("pk")]
    )
    form = tables.URLColumn(
        verbose_name="Form to Submit",
        accessor="task__resource",
    )
    date = tables.DateColumn(verbose_name="Due Date")

    class Meta:
        model = TaskDate
        fields = (
            "task_name",
            "form",
            "date",
            "task__owner",
            "task__description",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no tasks matching the search criteria..."

    def __init__(self, complete=True, *args, **kwargs):
        extra_columns = []
        if complete:
            extra_columns.extend(
                [
                    ("complete_link", tables.Column())
                ]
            )
        kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)

    def render_form(self, record):
        task = record.task
        value = task.render_task_link
        return value
    
    def render_complete_link(self, value):
        if value != 0:
            url = reverse('tasks:detail', args=[value])
            value = mark_safe(f'<a href="{url}" target="_blank">Completed Task Information</a>')
        else:
            value = "N/A"
        return value
