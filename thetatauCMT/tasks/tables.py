import django_tables2 as tables
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_tables2.utils import A

from core.tables import CMTTable

from .models import TaskDate


class TaskTable(CMTTable):
    task_name = tables.LinkColumn("tasks:complete", accessor="task__name", args=[A("pk")])
    # Plain Column, not URLColumn: render_form already returns a full <a>, and
    # URLColumn wrapped it in a second anchor, which the parser split into an
    # empty, unnamed link (WCAG 2.4.4 / axe "link-name").
    form = tables.Column(
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
            # empty_values=() ensures render_complete_link is called even when
            # the annotation is None (no completion for this chapter), so we
            # emit the "None" placeholder instead of the default em-dash.
            # orderable=False: ``complete_link`` is a per-chapter Subquery link,
            # not a real model field, so ``?sort=complete_link`` must never
            # reach the ORM (it raised FieldError otherwise — issue #1028).
            extra_columns.extend(
                [("complete_link", tables.Column(verbose_name="Complete Link", empty_values=(), orderable=False))]
            )
        kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)

    def render_form(self, record):
        task = record.task
        value = task.render_task_link
        return value

    def render_complete_link(self, value):
        if value:
            url = reverse("tasks:detail", args=[value])
            return mark_safe(f'<a href="{url}" target="_blank">Completed Task Information</a>')
        return mark_safe("<i>None</i>")
