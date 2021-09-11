import django_tables2 as tables
from django_tables2.utils import A
from .models import ChapterCurricula, Chapter


class ChapterCurriculaTable(tables.Table):
    class Meta:
        model = ChapterCurricula
        fields = ("major",)
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no curricula matching the search criteria..."


class ChapterTable(tables.Table):
    name = tables.LinkColumn("chapters:detail", args=[A("slug")])

    class Meta:
        model = Chapter
        fields = (
            "name",
            "region",
            "school",
            "address",
            "school_type",
            "council",
            "recognition",
            "website",
            "facebook",
        )

    def __init__(self, officer=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not officer:
            self.exclude = (
                "address",
                "council",
                "recognition",
            )

    # def render_recognition(self, value):
    #     return Chapter.RECOGNITION.get_value(value)


class AuditTable(tables.Table):
    item = tables.Column(
        "", attrs={"td": {"align": "left", "style": "font-weight:bold"}}
    )
    corresponding_secretary = tables.Column("Corr Sec")
    treasurer = tables.Column()
    scribe = tables.Column()
    vice_regent = tables.Column()
    regent = tables.Column()

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
            "td": {"align": "center"},
            "th": {"class": "text-center"},
        }
        orderable = False


class ChapterStatusTable(tables.Table):
    name = tables.TemplateColumn('<a href="{{ record.link }}">{{ record.name }}</a>')

    # Chapter, Members, Pledges, Events Last Month, Submissions Last Month, Current Balance, Tasks Overdue
    class Meta:
        model = Chapter
        fields = (
            "name",
            "balance",
            "balance_date",
            "officer_missing",
            "member_count",
            "pledge_count",
            "event_count",
            "tasks_overdue",
        )
        attrs = {
            "class": "table table-striped table-bordered",
            "td": {"align": "center"},
            "th": {"class": "text-center"},
        }
        orderable = False
