import django_tables2 as tables
from django_tables2.utils import A
from .models import ScoreType


class ScoreTable(tables.Table):
    name = tables.LinkColumn('scores:detail',
                             args=[A('slug')])
    score = tables.Column(empty_values=(),
                          verbose_name='Score')
    class Meta:
        model = ScoreType
        fields = ('name', 'description',
                  'section', 'points', 'type',
                  'score',
                  )
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no score types matching the search criteria..."

    def render_score(self, record, bound_row, table):
        score = record.chapter_score(self.request.user.chapter)
        return score
