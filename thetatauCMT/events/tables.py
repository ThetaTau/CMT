import django_tables2 as tables
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django.utils.text import Truncator

from core.tables import CMTTable

from .models import Event


class EventTable(CMTTable):
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
            "is_public",
            "parent_event",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no events matching the search criteria..."

    def __init__(self, natoff=False, *args, **kwargs):
        extra_columns = []
        if natoff:
            # National Officers see chapter context instead of the score column.
            remove = ["score"]
            for key in remove:
                if key in self.base_columns:
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
            return "None"
        url = record.parent_event.get_absolute_url()
        return mark_safe(f'<a href="{url}">{value}</a>')

    def render_description(self, value):
        """The description is rich text; a table cell only wants a plain summary."""
        return Truncator(strip_tags(value or "").strip()).chars(120) or "None"

    def render_chapter(self, value):
        """Link the (natoff-only) chapter column to the chapter detail page."""
        if not value:
            return "None"
        url = reverse("chapters:detail", kwargs={"slug": value.slug})
        return mark_safe(f'<a href="{url}">{value}</a>')

    def render_chapter__region(self, value, record):
        """Link the (natoff-only) region column to the region detail page."""
        if not value or not record.chapter_id:
            return value or "None"
        url = reverse("regions:detail", kwargs={"slug": record.chapter.region.slug})
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
