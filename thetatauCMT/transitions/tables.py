"""TRWI-9: compliance dashboard tables."""

import django_tables2 as tables

from core.tables import CMTTable

from .models import ReportObligation


class ObligationComplianceTable(CMTTable):
    """One row per ``ReportObligation`` -- the chapter dashboard (TRWI-9).

    ``acknowledged`` reads the queryset's own ``acknowledged`` annotation
    (an ``Exists`` subquery -- see ``views.ChapterComplianceView``), not a
    per-row lookup, so this table never causes extra queries per row.
    "Missed" rows get a red highlight (``row_attrs``) -- the spec's own
    "primary accountability lever".
    """

    position_key = tables.Column(verbose_name="Position")
    officer = tables.Column(verbose_name="Officer", accessor="officer__name", order_by="officer__name")
    status = tables.Column(verbose_name="Status")
    due_date = tables.DateColumn(verbose_name="Due")
    acknowledged = tables.BooleanColumn(verbose_name="Acknowledged", yesno="Yes,No")

    class Meta:
        model = ReportObligation
        fields = ("position_key", "officer", "status", "due_date", "acknowledged")
        attrs = {"class": "table table-striped table-bordered"}
        row_attrs = {"class": lambda record: "table-danger" if record.status == "missed" else ""}
        empty_text = "No Transition Report obligations for this chapter in this cycle."
        order_by = "-due_date"

    def render_position_key(self, value):
        return value.title()

    def render_status(self, record):
        return record.get_status_display()


class ChapterRateTable(CMTTable):
    """One row per ``services.ChapterComplianceStats`` (TRWI-9 regional/
    national rates view) -- backed by a plain list of dataclasses, not a
    queryset, so there is no ``Meta.model`` here.
    """

    chapter = tables.Column(verbose_name="Chapter", accessor="chapter__name", order_by="chapter__name")
    total = tables.Column(verbose_name="Obligations")
    submitted = tables.Column(verbose_name="Submitted")
    missed = tables.Column(verbose_name="Missed")
    submission_rate = tables.Column(verbose_name="Submission Rate")
    acknowledgment_rate = tables.Column(verbose_name="Acknowledgment Rate")

    class Meta:
        attrs = {"class": "table table-striped table-bordered"}
        row_attrs = {"class": lambda record: "table-danger" if record.missed else ""}
        empty_text = "No chapters to show for this cycle."
        order_by = "chapter"

    def render_submission_rate(self, value):
        return "None" if value is None else f"{value}%"

    def render_acknowledgment_rate(self, value):
        return "None" if value is None else f"{value}%"
