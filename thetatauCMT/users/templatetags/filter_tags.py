from django import template
from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


def _display_scalar(field, value):
    if hasattr(field, "choices") and field.choices:
        for choice_value, choice_label in field.choices:
            if str(choice_value) == str(value):
                return str(choice_label)
    if isinstance(field, (ModelChoiceField, ModelMultipleChoiceField)):
        try:
            obj = field.queryset.filter(pk=value).first()
        except (ValueError, TypeError):
            obj = None
        if obj is not None:
            return str(obj)
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return str(value)


def _display_value(bound_field):
    field = bound_field.field
    value = bound_field.value()
    if value in (None, ""):
        return ""
    if isinstance(value, (list, tuple)):
        parts = [_display_scalar(field, v) for v in value if v not in (None, "")]
        return ", ".join(p for p in parts if p)
    return _display_scalar(field, value)


def _active_summary(filterset):
    if filterset is None or not hasattr(filterset, "form"):
        return ""
    chips = []
    for bound_field in filterset.form:
        display = _display_value(bound_field)
        if not display:
            continue
        label = bound_field.label
        if not label or label == "[invalid name]":
            label = bound_field.name.replace("__icontains", "").replace("_", " ").title()
        chips.append(
            format_html(
                '<span class="filter-chip"><span class="filter-chip-label">{}:</span> '
                '<span class="filter-chip-value">{}</span></span>',
                label,
                display,
            )
        )
    return mark_safe("".join(chips))


def _filter_has_active_values(filterset):
    if filterset is None or not hasattr(filterset, "form"):
        return False
    for bound_field in filterset.form:
        value = bound_field.value()
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple)) and not any(v not in (None, "") for v in value):
            continue
        return True
    return False


@register.inclusion_tag("_partials/collapsible_filter.html", takes_context=True)
def collapsible_filter(context, filterset, label="Filter", collapse_id="filterCollapse"):
    request = context.get("request")
    return {
        "filterset": filterset,
        "label": label,
        "collapse_id": collapse_id,
        "active": _filter_has_active_values(filterset),
        "summary": _active_summary(filterset),
        "reset_url": request.path if request is not None else "",
    }
