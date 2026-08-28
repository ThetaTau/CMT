from django import template
from django.forms import ModelChoiceField, ModelMultipleChoiceField
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


def _iter_choices(field):
    """Yield flat ``(value, label)`` choice pairs for ``field``, if it has any.

    Never takes the length of the choices: a filter whose ``choices`` is a
    callable gets a ``CallableChoiceIterator``, and django_filters' wrapping
    ``ChoiceIterator.__len__`` blows up on it (so even ``if field.choices``
    raises). Grouped choices are flattened to their inner pairs.
    """
    choices = getattr(field, "choices", None)
    if choices is None:
        return
    try:
        pairs = list(choices)
    except TypeError:
        return
    for choice_value, choice_label in pairs:
        if isinstance(choice_label, (list, tuple)):
            yield from choice_label
        else:
            yield choice_value, choice_label


def _display_scalar(field, value):
    for choice_value, choice_label in _iter_choices(field):
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
def collapsible_filter(context, filterset, label="Filter", collapse_id="filterCollapse", reset_url=None):
    request = context.get("request")
    if reset_url is None:
        # Default: reload the page with no query string. Callers whose list has a
        # view-injected default filter (e.g. the officer roster's "current")
        # pass an explicit reset_url (like "?cancel=1") so "Clear Filter" truly
        # clears every filter, including that default.
        reset_url = request.path if request is not None else ""
    return {
        "filterset": filterset,
        "label": label,
        "collapse_id": collapse_id,
        "active": _filter_has_active_values(filterset),
        "summary": _active_summary(filterset),
        "reset_url": reset_url,
    }


@register.filter
def can_edit_role(record, user):
    """Template helper: ``True`` if ``user`` may edit ``record``'s term dates.

    Wraps :meth:`UserRoleChange.can_be_edited_by` so officer tables can gate the
    per-row Edit control.
    """
    try:
        return record.can_be_edited_by(user)
    except AttributeError:
        return False


@register.filter
def contact_visibility_short(value):
    """Compact badge label for a contact-visibility level."""
    from thetatauCMT.users.models import CONTACT_VISIBILITY_SHORT_LABELS

    return CONTACT_VISIBILITY_SHORT_LABELS.get(value, "")
