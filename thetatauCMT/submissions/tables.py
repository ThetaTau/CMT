import django_tables2 as tables
from django_tables2.utils import A
from .models import Submission, GearArticle


class SubmissionTable(tables.Table):
    name = tables.LinkColumn("submissions:update", args=[A("pk")])

    class Meta:
        model = Submission
        fields = (
            "name",
            "date",
            "type",
            "score",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no submissions matching the search criteria..."


class GearArticleTable(tables.Table):
    date = tables.DateColumn(verbose_name="Submit Date")
    title = tables.LinkColumn(
        "submissions:gear_detail", args=[A("pk")], verbose_name="Title"
    )
    chapter = tables.Column()
    pictures_count = tables.Column()

    class Meta:
        model = GearArticle
        order_by = "chapter"
        attrs = {"class": "table table-striped table-bordered"}
        fields = [
            "title",
            "reviewed",
            "chapter",
            "date",
            "notes",
            "pictures_count",
        ]
