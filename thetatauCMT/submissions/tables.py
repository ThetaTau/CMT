import django_tables2 as tables
from django_tables2.utils import A
from .models import Submission


class FileURLColumn(tables.LinkColumn):
    def compose_url(self, record, *args, **kwargs):
        return record.file.url


class SubmissionTable(tables.Table):
    name = tables.LinkColumn('submissions:update',
                             args=[A('pk')])
    file = FileURLColumn()

    class Meta:
        model = Submission
        fields = ('name', 'date',
                  'type', 'score', 'file')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no submissions matching the search criteria..."
