import django_tables2 as tables
from .models import ChapterCurricula


class ChapterCurriculaTable(tables.Table):
    class Meta:
        model = ChapterCurricula
        fields = ('major',
                  )
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no curricula matching the search criteria..."
