import django_tables2 as tables
from django_tables2.utils import A

from .models import User, UserOrgParticipate, UserStatusChange


class UserTable(tables.Table):
    rmp_complete = tables.Column(verbose_name="RMP Complete")

    class Meta:
        model = User
        fields = (
            "chapter",
            "preferred_pronouns",
            "name",
            "badge_number",
            "email",
            "rmp_complete",
            "major",
            "graduation_year",
            "phone_number",
            "current_status",
            "current_roles",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = (
            "There are no members matching the search criteria...\n"
            + "Only officers can view alumni contact information."
        )

    def __init__(self, chapter=False, natoff=False, admin=False, extra_info=False, rmp=False, *args, **kwargs):
        extra_columns = kwargs.get("extra_columns", [])
        # Everyone (chapter member, officer, natoff, admin) links through the
        # public member profile page. Admins still see the backend admin link
        # rendered on the profile page itself.
        self.base_columns["name"] = tables.LinkColumn("users:profile", kwargs={"username": A("username")})
        if admin:
            extra_columns.extend(
                [
                    ("full_address", tables.Column(accessor="address")),
                    ("id", tables.Column()),
                ]
            )
        if not rmp:
            self.base_columns["rmp_complete"].visible = False
        else:
            self.base_columns["rmp_complete"].visible = True
        if extra_info:
            extra_columns.extend(
                [
                    ("address", tables.Column("Address")),
                    ("initiation", tables.Column("Initiation")),
                ]
            )
        if chapter:
            extra_columns.extend(
                [
                    ("chapter__region", tables.Column("Region")),
                    ("chapter__school", tables.Column("School")),
                ]
            )
        kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)

    def render_initiation(self, value):
        if value:
            value = value.date
        return value

    def render_current_roles(self, value):
        if value:
            value = ", ".join(value)
        return value

    def render_current_status(self, value):
        if value:
            value = UserStatusChange.STATUS.get_value(value)
        return value

    def render_address(self, value):
        if value:
            if hasattr(value, "locality"):
                value = value.locality
            else:
                value = ""
        return value


class RollBookTable(tables.Table):
    rollbook = tables.LinkColumn("forms:roll_book_page", args=[A("pk")], attrs={"a": {"target": "_blank"}})
    birth_place = tables.Column()
    other_degrees = tables.Column()
    major_name = tables.Column()

    class Meta:
        model = User
        fields = (
            "rollbook",
            "name",
            "email",
            "major_name",
            "graduation_year",
            "phone_number",
            "address_formatted",
            "birth_place",
            "birth_date",
            "other_degrees",
        )
        attrs = {"class": "table table-striped table-bordered"}


class UserOrgTable(tables.Table):
    user = tables.LinkColumn(
        "users:profile",
        kwargs={"username": A("user__username")},
        accessor="user__name",
        verbose_name="Member",
    )
    organization = tables.Column(verbose_name="Organization", accessor="organization__name")
    officer = tables.BooleanColumn(verbose_name="Officer")
    remove = tables.TemplateColumn(
        template_name="users/org_remove_button.html",
        orderable=False,
        verbose_name="",
    )

    class Meta:
        model = UserOrgParticipate
        fields = (
            "user",
            "organization",
            "type",
            "officer",
            "start",
            "end",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "No external organization participation has been submitted for this chapter yet."
