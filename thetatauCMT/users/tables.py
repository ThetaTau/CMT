import django_tables2 as tables
from django_tables2.utils import A
from .models import User


class UserTable(tables.Table):
    class Meta:
        model = User
        fields = (
            "name",
            "badge_number",
            "email",
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
