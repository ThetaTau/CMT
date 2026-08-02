import django_tables2 as tables
from django_tables2.utils import A

from core.tables import CMTTable

from .models import ChapterNote, UserNote


class ChapterNoteTable(CMTTable):
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


class UserNoteTable(CMTTable):
    note = tables.TemplateColumn("{% load custom_tags %}{{ value|sanitize_html }}")

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
