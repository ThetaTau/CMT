import django_tables2 as tables
from django_tables2.utils import A
from .models import Objective


class ObjectiveTable(tables.Table):
    title = tables.LinkColumn("objectives:detail", args=[A("pk")])
    description = tables.TemplateColumn("{{ value|safe }}")
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
