import django_tables2 as tables
from django_tables2.utils import A
from .models import TaskDate


class TaskTable(tables.Table):
    task_name = tables.LinkColumn('tasks:complete',
                                  accessor='task.name',
                                  args=[A('pk')])
    date = tables.DateColumn(verbose_name="Due Date")
    form = tables.URLColumn(verbose_name="External\nForm to\nSubmit",
                            accessor='task.resource')

    class Meta:
        model = TaskDate
        fields = ('task_name', 'date', 'task.owner', 'task.description', 'form')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no tasks matching the search criteria..."

    def render_form(self, record):
        resource = record.task.resource
        if 'http' in resource:
            return resource
