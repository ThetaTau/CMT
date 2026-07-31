from django import template
from django.utils.safestring import mark_safe

from core.sanitize import sanitize_html as _sanitize_html

from ..forms import UserAlterForm

register = template.Library()


@register.filter(name="sanitize_html")
def sanitize_html(value):
    """Allow-list-sanitize user-authored rich text, then mark it safe.

    Use in place of ``|safe`` for any CKEditor / rich-text field so stored XSS
    payloads are stripped at render time.
    """
    return mark_safe(_sanitize_html(value or ""))


@register.simple_tag(takes_context=True)
def user_alter_form(context):
    request = context.get("request", None)
    if request:
        user = context["request"].user
        # Use *raw* natoff-group membership so the chapter/role switcher stays
        # available even while national-officer functionality is hidden.
        if not user.is_anonymous and user.in_national_officer_group:
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
            except Exception:
                continue
    return fields
