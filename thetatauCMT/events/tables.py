import django_tables2 as tables
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_tables2.utils import A
from .models import Event


class EventTable(tables.Table):
    name = tables.LinkColumn("events:update", args=[A("pk")])

    class Meta:
        model = Event
        order_by = "-date"
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

    def __init__(self, natoff=False, *args, **kwargs):
        extra_columns = []
        if natoff:
            remove = [
                "score",
                "members",
                "pledges",
                "alumni",
                "duration",
                "stem",
                "host",
                "virtual",
                "miles",
                "raised",
            ]
            for key in remove:
                self.base_columns[key].visible = False
            extra_columns.extend(
                [
                    ("chapter", tables.Column("Chapter")),
                    ("chapter.region", tables.Column("Region")),
                    ("pictures", tables.Column("Pictures")),
                ]
            )
        kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)

    def render_pictures(self, value):
        out = ""
        pictures = value.all()
        if pictures:
            for picture in pictures:
                if picture.image.name:
                    value = (
                        f'<a title="{picture.description}" href="{picture.image.url}" target="_blank">'
                        f'<img src="{picture.image.url}" width="150" height="150"/></a>'
                    )
                    out += value
        return mark_safe(out)
