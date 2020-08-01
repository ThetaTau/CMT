import django_tables2 as tables
from django_tables2.utils import A
from django.shortcuts import reverse
from django.utils.text import slugify
from django.utils.html import mark_safe
from .models import TaskDate


class TaskTable(tables.Table):
    task_name = tables.LinkColumn(
        "tasks:complete", accessor="task.name", args=[A("pk")]
    )
    date = tables.DateColumn(verbose_name="Due Date")
    complete_result = tables.LinkColumn(
        "tasks:detail",
        args=[A("complete_link")],
        verbose_name="Complete",
        empty_values=(),
    )

    class Meta:
        model = TaskDate
        fields = (
            "task_name",
            "date",
            "task.owner",
            "task.description",
            "complete_result",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no tasks matching the search criteria..."


class TaskIncompleteTable(tables.Table):
    task_name = tables.LinkColumn(
        "tasks:complete", accessor="task.name", args=[A("pk")]
    )
    date = tables.DateColumn(verbose_name="Due Date")
    form = tables.URLColumn(verbose_name="Form to Submit", accessor="task.resource")

    class Meta:
        model = TaskDate
        fields = ("task_name", "date", "task.owner", "task.description", "form")
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no tasks matching the search criteria..."

    def render_form(self, record):
        resource = record.task.resource
        if "http" in resource:
            return resource
        elif ":" in resource:
            if "ballot" in resource:
                value = mark_safe(
                    "<a href="
                    + reverse(resource, args=(slugify(record.task.name),))
                    + ">Ballot</a>"
                )
            else:
                value = mark_safe("<a href=" + reverse(resource) + ">Form</a>")
            return value
