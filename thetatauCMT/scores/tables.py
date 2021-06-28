import django_tables2 as tables
from django_tables2.utils import A
from .models import ScoreType
from core.models import BIENNIUM_YEARS


class ScoreTable(tables.Table):
    name = tables.LinkColumn("scores:detail", args=[A("slug")])
    total = tables.Column("Biennium Total")
    points = tables.Column("Points/Year")

    class Meta:
        model = ScoreType
        fields = (
            "name",
            "description",
            "section",
            "points",
            "type",
            "score1",
            "score2",
            "score3",
            "score4",
            "total",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no score types matching the search criteria..."

    def __init__(self, *args, **kwargs):
        start_year = kwargs.pop("start_year")
        adds = [0, 1, 1, 2]
        if start_year is None:
            start_year = BIENNIUM_YEARS[0]
        start_year = int(start_year)
        for i in range(4):
            # it is always fall year+0, spring year+1, fall year+1, spring year+2
            year = start_year + adds[i]
            semester = "Spring" if i % 2 else "Fall"
            self.base_columns[f"score{i + 1}"].verbose_name = f"{semester} {year}"
        super().__init__(*args, **kwargs)

    def render_section(self, value):
        return ScoreType.SECTION.get_value(value)

    def render_type(self, value):
        return ScoreType.TYPES.get_value(value)


class ChapterScoreTable(tables.Table):
    chapter_name = tables.Column()
    region = tables.Column()
    brotherhood = tables.Column(accessor="Bro")
    operate = tables.Column(accessor="Ops")
    professional = tables.Column(accessor="Pro")
    service = tables.Column(accessor="Ser")
    total = tables.Column()

    class Meta:
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no chapter scores matching the search criteria..."
