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
    field_name = Field(column_name="field_name")

    class Meta:
        model = User
        skip_unchanged = True
        report_skipped = False
        import_id_fields = ("user_id", "email")
        exclude = ("user_id",)

    def before_import(self, dataset, using_transactions, dry_run, **kwargs):
        dataset.headers = [header.strip() for header in dataset.headers]
        UserResource.Meta.fields = dataset.headers
        attrs = dict(vars(UserResource))
        new = resources.ModelDeclarativeMetaclass.__new__(
            resources.ModelDeclarativeMetaclass,
            "UserResource",
            (resources.ModelResource,),
            attrs,
        )
        self.fields = new.fields

    def init_instance(self, row=None):
        raise ValidationError(f"There is no user with id {row['user_id']}")

    def after_import(self, dataset, result, using_transactions, dry_run, **kwargs):
        result.diff_headers = self.get_diff_headers()

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
