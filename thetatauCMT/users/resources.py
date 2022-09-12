from django.db.models import Q
from django.core.exceptions import ValidationError
from import_export import resources
from import_export.fields import Field
from .models import UserRoleChange, User


class UserRoleChangeResource(resources.ModelResource):
    chapter = Field("user__chapter__name")
    school = Field("user__chapter__school")

    class Meta:
        model = UserRoleChange
        fields = (
            "user__name",
            "created",
            "role",
            "start",
            "end",
        )


class UserResource(resources.ModelResource):
    class Meta:
        model = User
        skip_unchanged = True
        report_skipped = False
        import_id_fields = ("user_id", "email")
        exclude = (
            "user_id",
            "address_changed",
            "chapter",
            "deceased_changed",
            "employer_address",
            "employer_changed",
            "major",
            "date_joined",
            "is_active",
            "is_staff",
            "user_permissions",
            "groups",
            "is_superuser",
            "last_login",
            "password",
            "id",
            "modified",
            "current_status",
            "current_roles",
        )

    def init_instance(self, row=None):
        raise ValidationError(f"There is no user with id {row['user_id']}")

    def get_instance(self, instance_loader, row):
        queries = []
        if "user_id" in row:
            queries.append(Q(user_id__iexact=row["user_id"]))
        if "email" in row:
            queries.append(Q(email_school__iexact=row["email"]))
            queries.append(Q(email__iexact=row["email"]))
        # Take one Q object from the list
        query = queries.pop()
        # Or the Q object with the ones remaining in the list
        for item in queries:
            query |= item
        try:
            instance = instance_loader.get_queryset().get(query)
        except self.Meta.model.DoesNotExist:
            return None
        except self.Meta.model.MultipleObjectsReturned:
            raise ValidationError(f"Multiple users found for {row}")
        else:
            return instance

    def before_import_row(self, row, row_number=None, **kwargs):
        if "user_id" in row:
            row["user_id"] = row["user_id"].strip()
        if "email" in row:
            row["email"] = row["email"].strip()
