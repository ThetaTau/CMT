import django_tables2 as tables
from .models import Invoice


class InvoiceTable(tables.Table):
    link = tables.TemplateColumn('<a href="{{record.link}}">Invoice Link</a>')
    description = tables.TemplateColumn("{{ value|safe }}")

    class Meta:
        model = Invoice
        fields = (
            "due_date",
            "description",
            "total",
        )
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
