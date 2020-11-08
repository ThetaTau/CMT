import django_tables2 as tables
from django_tables2.utils import A
from django.utils.html import mark_safe
from .models import (
    Guard,
    Badge,
    Depledge,
    StatusChange,
    Audit,
    PledgeProgram,
    ChapterReport,
    OSM,
    CollectionReferral,
)


class GuardTable(tables.Table):
    class Meta:
        model = Guard
        fields = (
            "name",
            "cost",
            "description",
            "letters",
        )
        attrs = {"class": "table table-striped table-bordered"}


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

    class Meta:
        model = PledgeProgram
        order_by = "chapter"
        attrs = {"class": "table table-striped table-bordered"}
        fields = [
            "chapter",
            "region",
            "school",
            "year",
            "term",
            "remote",
            "date_complete",
            "date_initiation",
            "weeks",
            "weeks_left",
            "status",
        ]

    def render_status(self, value):
        return PledgeProgram.STATUS.get_value(value)


class ChapterReportTable(tables.Table):
    class Meta:
        model = ChapterReport
        order_by = "chapter"
        attrs = {"class": "table table-striped table-bordered"}
        fields = [
            "chapter",
            "region",
            "year",
            "term",
            "report",
        ]


def get_value_from_a(value):
    """
    <a href="/tasks/detail/15/">True</a>    --> True
    <a href="/tasks/detail/0/">0</a>        --> N/A
    <a href="/tasks/detail/0/"></a>         --> False
    :param value:
    :return:
    """
    if "—" in value:
        return False
    elif "Complete" in value:
        return True
    return ""


class RiskFormTable(tables.Table):
    chapter = tables.Column(
        attrs={"td": {"align": "left", "style": "font-weight:bold"}}
    )
    all_complete = tables.BooleanColumn()
    region = tables.Column()
    corresponding_secretary = tables.LinkColumn(
        "forms:rmp_complete", kwargs={"pk": A("corresponding_secretary_pk")}
    )
    treasurer = tables.LinkColumn(
        "forms:rmp_complete", kwargs={"pk": A("treasurer_pk")}
    )
    scribe = tables.LinkColumn("forms:rmp_complete", kwargs={"pk": A("scribe_pk")})
    vice_regent = tables.LinkColumn(
        "forms:rmp_complete", kwargs={"pk": A("vice_regent_pk")}
    )
    regent = tables.LinkColumn("forms:rmp_complete", kwargs={"pk": A("regent_pk")})

    class Meta:
        attrs = {
            "class": "table table-striped table-bordered",
            "td": {"align": "center"},
            "td": {"complete": lambda value: get_value_from_a(value)},
            "th": {"class": "text-center"},
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
        model = ChapterReport
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
