import django_tables2 as tables
from django_tables2.utils import A
from .models import TaskDate


class TaskTable(tables.Table):
    # name = tables.LinkColumn('tasks:update',
    #                          args=[A('pk')])
    date = tables.DateColumn()

    class Meta:
        model = TaskDate
        fields = ('task.name', 'task.owner', 'task.description', 'date')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no tasks matching the search criteria..."

    # def render_date(self, record, bound_row, table):
    #     score = record.chapter_score(self.request.user.chapter)
    #     return score
