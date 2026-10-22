"""TRWI-9: compliance dashboard tables. TRWI-11: search & trend tables."""

import django_tables2 as tables

from core.tables import CMTTable


class ChapterRateTable(CMTTable):
    """One row per ``services.ChapterComplianceStats`` (TRWI-9 regional/
    national rates view) -- backed by a plain list of dataclasses, not a
    queryset, so there is no ``Meta.model`` here.
    """

    chapter = tables.Column(verbose_name="Chapter", accessor="chapter__name", order_by="chapter__name")
    total = tables.Column(verbose_name="Total Reports")
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


class ReportRowTable(CMTTable):
    """One row per ``services.ReportRow`` (2026-09 UI pass) -- the merged
    Search reports table: submitted reports the viewer may read, plus (when
    narrowed to one chapter) that chapter's other obligations with no
    readable report yet. Backed by a plain list of dataclasses (like
    ``ChapterRateTable``/``TagFrequencyTable``), not a queryset -- the rows
    already come from two different models, unified in
    ``services.get_report_rows`` rather than one shared query. "Missed" rows
    get the same red highlight the old chapter compliance table used.
    """

    position_key = tables.Column(verbose_name="Position", linkify=lambda record: record.link_url)
    chapter_name = tables.Column(verbose_name="Chapter", order_by="chapter_name")
    person = tables.Column(verbose_name="Person")
    status_display = tables.Column(verbose_name="Status", order_by="status")
    due_date = tables.DateColumn(verbose_name="Due")
    submitted_at = tables.DateTimeColumn(verbose_name="Submitted", format="N j, Y")
    acknowledged = tables.Column(verbose_name="Acknowledged")
    tag_list = tables.Column(verbose_name="Tags", orderable=False)

    class Meta:
        attrs = {"class": "table table-striped table-bordered"}
        row_attrs = {"class": lambda record: "table-danger" if record.status == "missed" else ""}
        empty_text = "No reports match your search."
        order_by = "-due_date"

    def render_position_key(self, value):
        return value.title()

    def render_acknowledged(self, value):
        if value is None:
            return "None"
        return "Yes" if value else "No"


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
