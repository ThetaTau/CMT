"""TRWI-9: compliance dashboard tables. TRWI-11: search & trend tables."""

import django_tables2 as tables

from core.tables import CMTTable

from .models import ReportObligation, TransitionReport


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


class SearchResultsTable(CMTTable):
    """One row per ``TransitionReport`` (TRWI-11 search results) -- a plain
    queryset table (unlike ``ChapterRateTable``/``TagFrequencyTable``), so
    sorting works directly off the underlying query.
    """

    chapter = tables.Column(verbose_name="Chapter", accessor="chapter__name", order_by="chapter__name")
    position_key = tables.Column(verbose_name="Position")
    author = tables.Column(verbose_name="Author", accessor="author__name", order_by="author__name")
    submitted_at = tables.DateTimeColumn(verbose_name="Submitted", format="N j, Y")
    tag_list = tables.Column(verbose_name="Tags", accessor="tag_list", orderable=False)

    class Meta:
        model = TransitionReport
        fields = ("chapter", "position_key", "author", "submitted_at", "tag_list")
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "No reports match your search."
        order_by = "-submitted_at"

    def render_position_key(self, value):
        return value.title()


class TagFrequencyTable(CMTTable):
    """One row per ``services.get_tag_frequency`` dict (TRWI-11 national
    trend view) -- backed by a plain list, not a queryset, so there is no
    ``Meta.model`` here (mirrors ``ChapterRateTable``).
    """

    tag_label = tables.Column(verbose_name="Tag", accessor="tag_label", order_by="tag_label")
    count = tables.Column(verbose_name="Reports")

    class Meta:
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "No tagged reports for this cycle."
        order_by = "-count"
