import django_tables2 as tables
from django.urls import reverse

from core.tables import CMTTable
from thetatauCMT.chapters.models import Chapter

from .models import Invoice

TERM_DISPLAY = {"fa": "Fall", "sp": "Spring", "wi": "Winter", "su": "Summer"}


class InvoiceTable(CMTTable):
    link = tables.TemplateColumn(
        '{%if record.link %}<a href="{{record.link}}" target="_blank">Invoice Link</a>{% endif %}'
    )
    description = tables.TemplateColumn("{% load custom_tags %}{{ value|sanitize_html }}")

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


class ChapterBalanceTable(CMTTable):
    chapter = tables.Column(
        verbose_name="Chapter",
        accessor="name",
        linkify=lambda record: reverse("chapters:detail", kwargs={"slug": record.slug}),
    )
    region = tables.Column(
        verbose_name="Region",
        accessor="region__name",
        linkify=lambda record: (
            reverse("regions:detail", kwargs={"slug": record.region.slug}) if record.region_id else None
        ),
    )
    actives_count = tables.Column(verbose_name="Actives")
    pnm_count = tables.Column(verbose_name="PNMs")
    open_balance = tables.Column(verbose_name="Balance")
    audit_dues_member = tables.Column(verbose_name="Member Dues (Audit)", empty_values=())
    audit_dues_pledge = tables.Column(verbose_name="PNM Pledging Fees / Dues (Audit)", empty_values=())
    audit_reported = tables.Column(
        verbose_name="Audit Reported",
        accessor="audit_created",
        empty_values=(),
        order_by=("audit_created",),
    )

    class Meta:
        model = Chapter
        fields = (
            "chapter",
            "region",
            "actives_count",
            "pnm_count",
            "open_balance",
            "audit_dues_member",
            "audit_dues_pledge",
            "audit_reported",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no chapters matching the search criteria..."

    @staticmethod
    def _money(amount):
        return f"${amount:,.2f}"

    def render_open_balance(self, value):
        return self._money(value)

    def render_audit_dues_member(self, record):
        amount = record.audit_dues_member
        if amount is None:
            return "None"
        frequency = record.audit_frequency or ""
        if frequency:
            return f"{self._money(amount)} / {frequency}"
        return self._money(amount)

    def render_audit_dues_pledge(self, value):
        if value is None:
            return "None"
        return self._money(value)

    def render_audit_reported(self, record):
        if not record.audit_year:
            return "None"
        term = TERM_DISPLAY.get(record.audit_term, record.audit_term or "")
        reported = f"{term} {record.audit_year}".strip()
        if record.audit_created:
            reported = f"{reported} ({record.audit_created:%Y-%m-%d})"
        return reported
