import django_tables2 as tables
from django_tables2.utils import A
from .models import ChapterNote, UserNote


class ChapterNoteTable(tables.Table):
    title = tables.LinkColumn("notes:detail", args=[A("pk")])

    class Meta:
        model = ChapterNote
        fields = (
            "title",
            "type",
            "file",
            "modified",
        )
        order_by = "-modified"
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no notes"


class UserNoteTable(tables.Table):
    note = tables.TemplateColumn("{{ value|safe }}")

    class Meta:
        model = UserNote
        fields = (
            "title",
            "note",
            "type",
            "file",
            "modified",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no notes"
