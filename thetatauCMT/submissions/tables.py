import django_tables2 as tables
from django_tables2.utils import A
from .models import Submission


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
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no submissions matching the search criteria..."
