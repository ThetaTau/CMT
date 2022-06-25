import django_tables2 as tables
from .models import Invoice


class InvoiceTable(tables.Table):
    link = tables.TemplateColumn(
        '{%if record.link %}<a href="{{record.link}}" target="_blank">Invoice Link</a>{% endif %}'
    )
    description = tables.TemplateColumn("{{ value|safe }}")

    class Meta:
        model = Invoice
        fields = (
            "due_date",
            "description",
            "total",
        )
        order_by = "-due_date"
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no invoices matching the search criteria..."


class ChapterBalanceTable(tables.Table):
    class Meta:
        model = Invoice
        fields = (
            "chapter",
            "region",
            "balance",
        )
