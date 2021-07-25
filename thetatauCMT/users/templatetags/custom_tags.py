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
                    "chapter": user.current_chapter.pk,
                    "role": new_role,
                }
            )
    return None
