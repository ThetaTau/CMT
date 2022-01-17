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


@register.simple_tag
def underscore(value, count):
    total = len(str(value))
    extra = count - total
    half_char = "_" * int(extra // 2.0)
    return mark_safe(f"{half_char}<u>{value}</u>{half_char}")
