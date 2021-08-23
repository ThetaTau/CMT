from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from django import forms
from .models import Event


class EventListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "event-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Events',
            Row(
                InlineField("name"),
                InlineField("date"),
                InlineField("type"),
                FormActions(
                    StrictButton(
                        '<i class="fa fa-search"></i> Filter',
                        type="submit",
                        css_class="btn-primary",
                    ),
                    Submit("cancel", "Clear", css_class="btn-primary"),
                ),
            ),
        ),
    )


class EventForm(forms.ModelForm):
    """
    This is a Model From created to add help text to the create
    event form without changing database model. The Duration field
    is the onlt field that is updated.
    """

    duration = forms.IntegerField(
        min_value=0,
        help_text="In Hours",
    )

    class Meta:
        model = Event
        fields = [
            "name",
            "date",
            "type",
            "description",
            "members",
            "pledges",
            "alumni",
            "guests",
            "duration",
            "stem",
            "host",
            "miles",
        ]
