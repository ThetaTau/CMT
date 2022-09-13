from django import template
from ..forms import UserAlterForm

register = template.Library()


@register.simple_tag(takes_context=True)
def user_alter_form(context):
    request = context.get("request", None)
    if request:
        user = context["request"].user
        if not user.is_anonymous and user.is_national_officer_group:
            new_role = None
            if user.altered.all():
                new_role = user.altered.first().role
            return UserAlterForm(
                data={
                    "chapter": user.current_chapter.slug,
                    "role": new_role,
                }
            )
    return None


@register.filter
def get_fields(obj):
    fields = []
    for field in obj._meta.get_fields():
        if hasattr(field, "verbose_name") and field.verbose_name not in [
            "ID",
            "Flow",
            "artifact content type",
            "artifact object id",
            "process ptr",
            "password",
            "superuser status",
            "staff status",
            "user permissions",
            "groups",
        ]:
            try:
                fields.append((field.verbose_name.title(), field.value_to_string(obj)))
            except:
                continue
    return fields
