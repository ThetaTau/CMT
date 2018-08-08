import django_tables2 as tables
from django_tables2.utils import A
from .models import TaskDate


class TaskTable(tables.Table):
    task_name = tables.LinkColumn('tasks:complete',
                                  accessor='task.name',
                                  args=[A('pk')])
    date = tables.DateColumn(verbose_name="Due Date")

    class Meta:
        model = TaskDate
        fields = ('task_name', 'date', 'task.owner', 'task.description')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no tasks matching the search criteria..."
