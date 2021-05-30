import django_tables2 as tables
from .models import ChapterNote, UserNote


class ChapterNoteTable(tables.Table):
    note = tables.TemplateColumn("{{ value|safe }}")

    class Meta:
        model = ChapterNote
        fields = (
            "title",
            "note",
            "type",
            "file",
            "modified",
        )
        order_by = "-modified"
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no notes"


class UserNoteTable(tables.Table):
    class Meta:
        model = UserNote
        fields = (
            "title",
            "note",
            "type",
            "file",
            "created",
            "modified",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no notes"
