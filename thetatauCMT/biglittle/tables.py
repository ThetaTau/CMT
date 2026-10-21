import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html
from django_tables2.utils import A

from core.tables import EMPTY_VALUE, CMTTable
from thetatauCMT.users.models import User, UserStatusChange

from . import services


class BigLittleMemberTable(CMTTable):
    name = tables.LinkColumn("users:profile", kwargs={"username": A("username")}, verbose_name="Member")
    badge_number = tables.Column(verbose_name="Roll")
    current_status = tables.Column(verbose_name="Status")
    initiation_date = tables.DateColumn(verbose_name="Initiated")
    big_name = tables.Column(verbose_name="Big")
    little_count = tables.Column(verbose_name="Littles")
    actions = tables.TemplateColumn(
        template_name="biglittle/_member_actions.html",
        orderable=False,
        verbose_name="",
    )

    class Meta:
        model = User
        fields = ("name", "badge_number", "current_status", "initiation_date", "big_name", "little_count")
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "No initiated members match these filters."

    def render_badge_number(self, value, record):
        return value if services.has_badge_number(record) else EMPTY_VALUE

    def render_current_status(self, value):
        return UserStatusChange.STATUS.get_value(value) or value

    def render_big_name(self, value, record):
        url = reverse("users:profile", kwargs={"username": record.big_username})
        return format_html('<a href="{}">{}</a>', url, value)
