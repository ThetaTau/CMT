import django_tables2 as tables
from django_tables2.utils import A
from .models import User


class UserTable(tables.Table):
    rmp_complete = tables.Column(verbose_name="RMP Complete")

    class Meta:
        model = User
        fields = (
            "name",
            "badge_number",
            "email",
            "rmp_complete",
            "major",
            "graduation_year",
            "phone_number",
            "current_status",
            "role",
            "role_end",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = (
            "There are no members matching the search criteria...\n"
            + "Only officers can view alumni contact information."
        )

    def __init__(
        self,
        chapter=False,
        natoff=False,
        admin=False,
        extra_info=False,
        *args,
        **kwargs
    ):
        extra_columns = []
        if admin:
            self.base_columns["name"] = tables.LinkColumn(
                "admin:users_user_change", kwargs={"object_id": A("id")}
            )
            extra_columns.extend(
                [
                    ("full_address", tables.Column(accessor="address")),
                ]
            )
        elif natoff:
            self.base_columns["name"] = tables.LinkColumn(
                "users:info", kwargs={"user_id": A("user_id")}
            )
        else:
            self.base_columns["name"] = tables.Column()
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
                    ("chapter", tables.Column("Chapter")),
                    ("chapter.region", tables.Column("Region")),
                    ("chapter.school", tables.Column("School")),
                ]
            )
        kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)

    def render_initiation(self, value):
        if value:
            value = value.date
        return value

    def render_address(self, value):
        if value:
            if hasattr(value, "locality"):
                value = value.locality
            else:
                value = ""
        return value


class RollBookTable(tables.Table):
    rollbook = tables.LinkColumn(
        "forms:roll_book_page", args=[A("pk")], attrs={"a": {"target": "_blank"}}
    )
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
