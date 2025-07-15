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


@register.filter(name="lookup")
def lookup(value, arg):
    if isinstance(value, dict):
        return_value = value.get(arg)
    else:
        return_value = getattr(value, arg)
    return return_value


@register.filter(name="split")
def split(value, key):
    return value.split(key)


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
