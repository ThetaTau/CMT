from django.utils.safestring import mark_safe
import django_tables2 as tables
from django_tables2.utils import A
from .models import (
    Badge,
    Depledge,
    StatusChange,
    Audit,
    PledgeProgram,
    Convention,
    ChapterEducation,
    OSM,
    CollectionReferral,
    PledgeProgramProcess,
)


class BadgeTable(tables.Table):
    class Meta:
        model = Badge
        fields = (
            "name",
            "cost",
            "description",
        )
        attrs = {"class": "table table-striped table-bordered"}


class PledgeFormTable(tables.Table):
    pledge = tables.DateColumn(verbose_name="Pledge Date")
    submitted = tables.DateColumn()
    status = tables.Column()
    pledge_names = tables.Column()

    class Meta:
        attrs = {"class": "table table-striped table-bordered"}


class InitiationTable(tables.Table):
    initiation = tables.DateColumn(verbose_name="Initiation Date")
    submitted = tables.DateColumn()
    status = tables.Column()
    member_names = tables.Column()

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }


class DepledgeTable(tables.Table):
    user = tables.Column(accessor="user.name")
    date = tables.DateColumn(verbose_name="Depledge Date")
    created = tables.DateColumn(verbose_name="Submitted")

    class Meta:
        model = Depledge
        fields = ("user", "date", "created")
        attrs = {"class": "table table-striped table-bordered"}


class StatusChangeTable(tables.Table):
    user = tables.Column(accessor="user.name")
    date_start = tables.DateColumn(verbose_name="Change Date")
    created = tables.DateColumn(verbose_name="Form Submitted")

    class Meta:
        model = StatusChange
        fields = ("user", "date_start", "created", "reason", "date_end")
        attrs = {"class": "table table-striped table-bordered"}


class AuditTable(tables.Table):
    debit_card_access = tables.Column("Debit Card Access")

    class Meta:
        model = Audit
        attrs = {"class": "table table-striped table-bordered"}
        order_by = "-modified"
        fields = [
            "user.chapter",
            "user.chapter.region",
            "modified",
            "dues_member",
            "dues_pledge",
            "frequency",
            "balance_checking",
            "balance_savings",
            "debit_card",
            "debit_card_access",
            "payment_plan",
            "cash_book",
            "cash_book_reviewed",
            "cash_register",
            "cash_register_reviewed",
            "member_account",
            "member_account_reviewed",
        ]


class PledgeProgramTable(tables.Table):
    date_complete = tables.DateColumn(verbose_name="Complete Date")
    date_initiation = tables.DateColumn(verbose_name="Initiation Date")
    remote = tables.BooleanColumn(verbose_name="Remote")
    weeks = tables.Column(verbose_name="Weeks in Program")
    weeks_left = tables.Column(verbose_name="Weeks LEFT in Program")
    status = tables.Column(verbose_name="Program Status")
    approval = tables.Column()
    chapter_name = tables.Column(verbose_name="Chapter")
    pk = tables.LinkColumn(
        "forms:pledge_program_detail", verbose_name="Link", args=[A("pk")]
    )

    class Meta:
        model = PledgeProgram
        order_by = "chapter"
        attrs = {"class": "table table-striped table-bordered"}
        fields = [
            "chapter_name",
            "region",
            "school",
            "year",
            "term",
            "pk",
            "manual",
            "approval",
            "remote",
            "date_complete",
            "date_initiation",
            "weeks",
            "weeks_left",
            "status",
        ]

    def render_status(self, value):
        return PledgeProgram.STATUS.get_value(value)

    def render_term(self, value):
        return PledgeProgram.TERMS.get_value(value)

    def render_manual(self, value):
        return PledgeProgram.MANUALS.get_value(value)

    def render_approval(self, value):
        if value == "not_submitted":
            return "Not Submitted"
        else:
            return PledgeProgramProcess.APPROVAL.get_value(value)


class ChapterEducationListTable(tables.Table):
    chapter_name = tables.Column()
    region = tables.Column()
    alcohol_drugs = tables.FileColumn(verbose_name="Alcohol and Drug Awareness")
    harassment = tables.FileColumn(verbose_name="Anti-Harassment")
    mental = tables.FileColumn(verbose_name="Mental Health Recognition")

    class Meta:
        model = ChapterEducation
        order_by = "chapter_name"
        attrs = {"class": "table table-striped table-bordered"}
        fields = [
            "chapter_name",
            "region",
            "alcohol_drugs",
            "harassment",
            "mental",
        ]

    def render_alcohol_drugs(self, value, column, record, bound_column):
        if value:
            value = "<br>".join(
                [
                    f"{approval}: {bound_column.link(column.render(record, program), value=program, record=record)}"
                    for approval, program in value
                ]
            )
            if "Approved" in value:
                column.attrs = {"td": {"bgcolor": "#40B0A6"}}
            elif "Revisions" in value or "Denied" in value:
                column.attrs = {"td": {"bgcolor": "#E1BE6A"}}
            else:
                column.attrs = {"td": {}}
        else:
            value = ""
        return mark_safe(value)

    def render_harassment(self, value):
        if value:
            value = value[0]
        else:
            value = ""
        return value

    def render_mental(self, value):
        if value:
            value = value[0]
        else:
            value = ""
        return value


class ChapterEducationTable(tables.Table):
    category = tables.Column()
    approval_comments = tables.Column(verbose_name="Review Comments")
    program_date = tables.DateColumn()

    class Meta:
        model = ChapterEducation
        order_by = "program_date"
        attrs = {"class": "table table-striped table-bordered"}
        fields = [
            "program_date",
            "category",
            "approval",
            "approval_comments",
            "report",
        ]

    # def render_approval(self, value):
    #     return ChapterEducation.APPROVAL.get_value(value)


class RiskFormTable(tables.Table):
    chapter = tables.Column(
        attrs={"td": {"align": "left", "style": "font-weight:bold"}}
    )
    region = tables.Column()
    complete = tables.Column()
    incomplete = tables.Column()

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }
        # orderable = False


class PrematureAlumnusStatusTable(tables.Table):
    user = tables.Column()
    status = tables.Column()
    approved = tables.Column()
    created = tables.DateColumn()

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }


class ReturnStudentStatusTable(tables.Table):
    user = tables.Column()
    status = tables.Column()
    approved = tables.Column()
    created = tables.DateColumn()

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }


class DisciplinaryStatusTable(tables.Table):
    user = tables.Column(verbose_name="Name of Accused")
    status = tables.Column()
    approved = tables.Column()
    created = tables.DateColumn()
    trial_date = tables.DateColumn()
    link = tables.TemplateColumn(
        '{% if record.link %}<a href="{{ record.link }}">Form 2 Link</a>{% endif %}'
    )

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }


class PledgeProgramStatusTable(tables.Table):
    status = tables.Column()
    approved = tables.Column()
    created = tables.DateColumn()
    term = tables.LinkColumn("forms:pledge_program_detail", args=[A("pk")])

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }

    def render_term(self, value):
        if value:
            term, year = value.split(" ")
            return f"{PledgeProgram.TERMS.get_value(term)} {year}"
        return value


class SignTable(tables.Table):
    member = tables.Column()
    owner = tables.Column(verbose_name="Task Owner")
    role = tables.Column()
    status = tables.Column()
    approved = tables.Column()
    link = tables.TemplateColumn(
        '{% if record.link %}<a href="{{ record.link }}">Sign Link</a>{% endif %}'
    )

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }


class ConventionListTable(tables.Table):
    class Meta:
        model = Convention
        order_by = "chapter"
        attrs = {"class": "table table-striped table-bordered"}
        fields = [
            "chapter",
            "region",
            "year",
            "term",
            "delegate",
            "alternate",
        ]


class OSMListTable(tables.Table):
    class Meta:
        model = OSM
        order_by = "chapter"
        attrs = {"class": "table table-striped table-bordered"}
        fields = [
            "chapter",
            "region",
            "year",
            "term",
            "nominate",
        ]


class CollectionReferralTable(tables.Table):
    user = tables.Column(verbose_name="Indebted Member", accessor="user.name")
    created = tables.DateColumn(verbose_name="Submitted")

    class Meta:
        model = CollectionReferral
        fields = ("user", "created")
        attrs = {"class": "table table-striped table-bordered"}


class ResignationStatusTable(tables.Table):
    description = tables.Column()
    owner = tables.Column()
    started = tables.Column()
    finished = tables.Column()
    status = tables.Column()

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }


class ResignationListTable(tables.Table):
    member = tables.Column()
    finished = tables.Column()
    status = tables.Column()
    link = tables.TemplateColumn('<a href="{{ record.link }}">Sign Link</a>')

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
        }
