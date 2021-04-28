from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def safeURLfile(value):
    try:
        value.url
    except (ValueError, AttributeError):
        return value
    else:
        return mark_safe(f'<a href="{value.url}" target="_blank">{value.name}</a>')
