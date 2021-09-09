import django_tables2 as tables
from django_tables2.utils import A
from .models import Event


class EventTable(tables.Table):
    name = tables.LinkColumn("events:update", args=[A("pk")])

    class Meta:
        model = Event
        fields = (
            "name",
            "date",
            "type",
            "score",
            "description",
            "members",
            "pledges",
            "alumni",
            "duration",
            "stem",
            "host",
            "virtual",
            "miles",
            "raised",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no events matching the search criteria..."
