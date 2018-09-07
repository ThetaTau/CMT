import django_tables2 as tables
from django_tables2.utils import A
from .models import ScoreType


class ScoreTable(tables.Table):
    name = tables.LinkColumn('scores:detail',
                             args=[A('slug')])

    class Meta:
        model = ScoreType
        fields = ('name', 'description',
                  'section', 'points', 'type',
                  'score',
                  )
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no score types matching the search criteria..."
