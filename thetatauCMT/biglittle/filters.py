import django_filters
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Submit

from core.models import ACTIVE_STATUSES, ALUMNI_STATUSES
from thetatauCMT.users.filters import filter_name_or_maiden_name
from thetatauCMT.users.models import User


class BigLittleMemberFilter(django_filters.FilterSet):
    name__icontains = django_filters.CharFilter(method=filter_name_or_maiden_name, label="Member Name contains")
    status = django_filters.ChoiceFilter(
        label="Member Status",
        choices=(("active", "Active"), ("alumni", "Alumni")),
        method="filter_status",
        empty_label="All statuses",
    )
    big = django_filters.ChoiceFilter(
        label="Big",
        choices=(("yes", "Big recorded"), ("no", "No Big recorded")),
        method="filter_big",
        empty_label="With or without a Big",
    )

    class Meta:
        model = User
        fields = []

    def filter_status(self, queryset, name, value):
        if value == "active":
            return queryset.filter(current_status__in=ACTIVE_STATUSES)
        if value == "alumni":
            return queryset.filter(current_status__in=ALUMNI_STATUSES)
        return queryset

    def filter_big(self, queryset, name, value):
        if value in ("yes", "no"):
            return queryset.filter(link_pk__isnull=value == "no")
        return queryset


class BigLittleListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "big-little-search-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True

    def __init__(self, form=None):
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter Members',
                Row(
                    InlineField("name__icontains"),
                    InlineField("status"),
                    InlineField("big"),
                    FormActions(
                        StrictButton('<i class="fa fa-search"></i> Filter', type="submit", css_class="btn-primary"),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    ),
                ),
            ),
        )
        super().__init__(form=form)
