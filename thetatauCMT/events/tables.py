import django_tables2 as tables
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import Event


class EventTable(tables.Table):
    name = tables.Column(linkify=lambda record: record.get_absolute_url())
    is_public = tables.BooleanColumn(verbose_name="Open to Other Chapters")
    parent_event = tables.Column(verbose_name="Parent Event")

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
            "is_public",
            "parent_event",
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
                    ("chapter__region", tables.Column("Region")),
                    ("pictures", tables.Column("Pictures")),
                ]
            )
        kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)

    def render_parent_event(self, value, record):
        if not record.parent_event_id:
            return "—"
        url = record.parent_event.get_absolute_url()
        return mark_safe(f'<a href="{url}">{value}</a>')

    def render_chapter(self, value):
        """Link the (natoff-only) chapter column to the chapter detail page."""
        if not value:
            return "—"
        url = reverse("chapters:detail", kwargs={"slug": value.slug})
        return mark_safe(f'<a href="{url}">{value}</a>')

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
