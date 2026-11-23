from django import template

from ..judging import ordinal as ordinal_number

register = template.Library()


@register.filter
def ordinal(value):
    """``1`` as ``1st``; empty stays empty."""
    if value in (None, ""):
        return ""
    return ordinal_number(int(value))
