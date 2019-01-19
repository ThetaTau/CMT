from django import template
from ..forms import UserAlterForm
from ..models import UserAlterChapter

register = template.Library()


@register.simple_tag(takes_context=True)
def user_alter_form(context):
    request = context.get('request', None)
    if request:
        user = context['request'].user
        if not user.is_anonymous and user.is_national_officer_group:
            return UserAlterForm(data={'chapter': user.current_chapter.pk})
    return None
