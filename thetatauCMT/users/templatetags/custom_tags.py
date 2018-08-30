from django import template
from ..forms import UserAlterForm
from ..models import UserAlterChapter

register = template.Library()


@register.simple_tag(takes_context=True)
def user_alter_form(context):
    user = context['request'].user
    return UserAlterForm(data={'chapter': user.current_chapter.pk})
