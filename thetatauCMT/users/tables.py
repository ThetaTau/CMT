from django.conf import settings
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

    def __init__(self, chapter=False, *args, **kwargs):
        extra_columns = None
        if chapter:
            extra_columns = [
                ("chapter", tables.Column("Chapter")),
                ("chapter.region", tables.Column("Region")),
            ]
        super().__init__(extra_columns=extra_columns, *args, **kwargs)
