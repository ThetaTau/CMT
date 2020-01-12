import django_tables2 as tables
from django_tables2.utils import A
from .models import ScoreType
from core.models import BIENNIUM_YEARS


class ScoreTable(tables.Table):
    name = tables.LinkColumn('scores:detail',
                             args=[A('slug')])
    total = tables.Column('Biennium Total')

    class Meta:
        model = ScoreType
        fields = ('name', 'description',
                  'section', 'points', 'type',
                  'score1', 'score2', 'score3', 'score4', 'total',
                  )
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no score types matching the search criteria..."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for i in range(4):
            year = BIENNIUM_YEARS[i]
            semester = 'Spring' if i % 2 else 'Fall'
            self.base_columns[f'score{i + 1}'].verbose_name = f"{semester} {year}"

    def render_section(self, value):
        return ScoreType.SECTION.get_value(value)

    def render_type(self, value):
        return ScoreType.TYPES.get_value(value)


class ChapterScoreTable(tables.Table):
    chapter_name = tables.Column()
    region = tables.Column()
    brotherhood = tables.Column(accessor='Bro')
    operate = tables.Column(accessor='Ops')
    professional = tables.Column(accessor='Pro')
    service = tables.Column(accessor='Ser')
    total = tables.Column()

    class Meta:
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no chapter scores matching the search criteria..."
