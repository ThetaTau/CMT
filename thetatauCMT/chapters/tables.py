import django_tables2 as tables
from django_tables2.utils import A
from .models import ChapterCurricula, Chapter


class ChapterCurriculaTable(tables.Table):
    class Meta:
        model = ChapterCurricula
        fields = ('major',
                  )
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no curricula matching the search criteria..."


class ChapterTable(tables.Table):
    name = tables.LinkColumn('chapters:detail',
                             args=[A('slug')])

    class Meta:
        model = Chapter
        fields = (
            'name',
            'region',
            'school',
            'website',
            'facebook',
        )
