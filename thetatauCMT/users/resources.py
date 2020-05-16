from import_export import resources
from import_export.fields import Field
from .models import UserRoleChange


class UserRoleChangeResource(resources.ModelResource):
    chapter = Field("user__chapter__name")

    class Meta:
        model = UserRoleChange
        fields = (
            "user__name",
            "created",
            "role",
            "start",
            "end",
        )
