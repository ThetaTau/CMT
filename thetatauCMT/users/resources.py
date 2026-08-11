from django.core.exceptions import ValidationError
from django.db.models import Q
from import_export import resources
from import_export.fields import Field
from import_export.widgets import ManyToManyWidget

from .models import Position, User, UserRoleChange, UserStatusChange, UserTag


class UserTagResource(resources.ModelResource):
    # Semicolon-separated list of user PKs. On import the users listed here
    # are ADDED to the tag (m2m_add=True) — existing tagged users are kept,
    # so re-importing is idempotent. Tags are matched by their unique name
    # via ``import_id_fields``, so re-importing a row with an existing name
    # updates that tag instead of creating a duplicate.
    user_ids = Field(
        column_name="user_ids",
        attribute="users",
        widget=ManyToManyWidget(User, field="pk", separator=";"),
        m2m_add=True,
    )

    class Meta:
        model = UserTag
        fields = ("id", "name", "user_ids")
        export_order = ("id", "name", "user_ids")
        import_id_fields = ("name",)
        skip_unchanged = True


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
            "chapter",
            "school",
        )


class UserStatusChangeResource(resources.ModelResource):
    class Meta:
        model = UserStatusChange
        force_init_instance = True
        fields = (
            "user",
            "user__email",
            "status",
            "start",
            "end",
        )

    def before_import_row(self, row, row_number=None, **kwargs):
        user = User.objects.get(email=row["user__email"])
        row["user"] = user.id


class UserResource(resources.ModelResource):
    # Employer / positions are related records; export their names and keep them
    # out of imports (the same treatment `major` gets).
    employer_name = Field(attribute="employer__name", column_name="employer", readonly=True)
    positions = Field(
        attribute="employer_positions",
        column_name="employer_positions",
        widget=ManyToManyWidget(Position, field="name", separator="; "),
        readonly=True,
    )

    class Meta:
        model = User
        skip_unchanged = True
        report_skipped = False
        batch_size = 50
        use_bulk = True
        chunk_size = 50
        import_id_fields = ("id", "email")
        exclude = (
            "id",
            "address_changed",
            "chapter",
            "deceased_changed",
            "employer",
            "employer_address",
            "employer_changed",
            "employer_positions",
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
        message = "There is no user with:"
        if "id" in row:
            message = f"{message} id={row['id']}"
        if "email" in row:
            message = f"{message} email={row['email']}"
        raise ValidationError(message)

    def get_instance(self, instance_loader, row):
        queries = []
        if "id" in row and row["id"]:
            queries.append(Q(id__iexact=row["id"]))
        if "email" in row and row["email"]:
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
        if "email" in row:
            row["email"] = row["email"].strip()
