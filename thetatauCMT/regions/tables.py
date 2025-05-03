import django_tables2 as tables
from django.urls import reverse
from django.utils.safestring import mark_safe

def get_value_from_a(value):
    """
    <a href="/tasks/detail/15/">True</a>    --> True
    <a href="/tasks/detail/0/">0</a>        --> N/A
    <a href="/tasks/detail/0/"></a>         --> False
    :param value:
    :return:
    """
    if value == "": return False
    elif "a href=" in value: return True
    else: return ""

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
        if value != 0:
            url = reverse('tasks:detail', args=[value])
            value = mark_safe(f'<a href="{url}" target="_blank">Completed Task Information</a>')
        else:
            value = ""

        return value
