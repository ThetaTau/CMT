import django_tables2 as tables
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

    def __init__(self, chapter=False, *args, **kwargs):
        if chapter:
            extra_columns = [
                ("chapter", tables.Column("Chapter")),
                ("chapter.region", tables.Column("Region")),
                ("chapter.school", tables.Column("School")),
            ]
            kwargs["extra_columns"] = extra_columns
        super().__init__(*args, **kwargs)
