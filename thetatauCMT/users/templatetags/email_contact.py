from django import template
from configs.models import Config

register = template.Library()


@register.simple_tag
def contact(clean=False):
    return Config.get_value("HScontact", clean=clean)
