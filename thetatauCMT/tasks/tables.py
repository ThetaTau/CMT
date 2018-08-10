import django_tables2 as tables
from django_tables2.utils import A
from django.shortcuts import reverse
from django.utils.html import mark_safe
from .models import TaskDate


class TaskTable(tables.Table):
    task_name = tables.LinkColumn('tasks:complete',
                                  accessor='task.name',
                                  args=[A('pk')])
    date = tables.DateColumn(verbose_name="Due Date")
    complete = tables.BooleanColumn(
        accessor='chapters.submission_object',
        verbose_name="Complete", empty_values=())

    class Meta:
        model = TaskDate
        fields = ('task_name', 'date', 'task.owner',
                  'task.description', 'complete')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no tasks matching the search criteria..."

    def render_complete(self, record):
        complete = record.complete(self.request.user.chapter)
        if complete:
            return mark_safe('<a href='+reverse("tasks:detail", args=[complete[0].pk])+'>True</a>')
        return ''


class TaskIncompleteTable(tables.Table):
    task_name = tables.LinkColumn('tasks:complete',
                                  accessor='task.name',
                                  args=[A('pk')])
    date = tables.DateColumn(verbose_name="Due Date")
    form = tables.URLColumn(verbose_name="Form to Submit",
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
