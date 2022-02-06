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
        import_id_fields = ("user_id",)
        fields = ("user_id",)

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
        # self.fields.pop("field_name")
        # for header in dataset.headers:
        #     if header == "user_id":
        #         continue
        #     field = self.field_from_django_field(
        #         header, User._meta.get_field(header), readonly=False
        #     )
        #     self.fields[header] = field

    def init_instance(self, row=None):
        raise ValidationError(f"There is no user with id {row['user_id']}")

    def after_import(self, dataset, result, using_transactions, dry_run, **kwargs):
        result.diff_headers = self.get_diff_headers()
