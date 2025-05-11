import django_tables2 as tables
from django.urls import reverse
from django.utils.safestring import mark_safe


def get_value_from_a(value):
    if value == "":
        return False  # Task is incomplete
    elif value == "N/A":
        return "N/A"  # Task is N/A
    elif "Completed Task Information" in value:
        return True  # Task is complete
    else:
        return ""  # Value is not a task


class RegionChapterTaskTable(tables.Table):
    task_name = tables.Column("task_name")
    task_owner = tables.Column("task_owner")
    school_type = tables.Column("school_type")
    date = tables.DateColumn(verbose_name="Due Date")

    class Meta:
        attrs = {
            "class": "table table-striped table-hover",
            "td": {"complete": lambda value: get_value_from_a(value)},
        }


class TaskLinkColumn(tables.Column):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def render(self, value):
        if value is None:
            return "N/A"
        if value == 0:
            return ""

        url = reverse("tasks:detail", args=[value])

        return mark_safe(
            f'<a href="{url}" target="_blank">Completed Task Information</a>'
        )
