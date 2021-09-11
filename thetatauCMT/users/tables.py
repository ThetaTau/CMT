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

    def __init__(self, chapter=False, natoff=False, admin=False, *args, **kwargs):
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
        if chapter:
            extra_columns = [
                ("chapter", tables.Column("Chapter")),
                ("chapter.region", tables.Column("Region")),
                ("chapter.school", tables.Column("School")),
            ]
            kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)
