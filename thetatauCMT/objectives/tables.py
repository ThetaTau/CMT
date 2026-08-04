import django_tables2 as tables
from django_tables2.utils import A

from core.tables import CMTTable

from .models import Objective


class ObjectiveTable(CMTTable):
    title = tables.LinkColumn("objectives:detail", args=[A("pk")])
    description = tables.TemplateColumn("{% load custom_tags %}{{ value|sanitize_html }}")
    actions_count = tables.Column(verbose_name="Incomplete Actions")

    class Meta:
        model = Objective
        fields = (
            "title",
            "owner",
            "date",
            "complete",
            "actions_count",
            "description",
        )
        order_by = "-date"
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no goals"
