from crispy_forms.bootstrap import Field, FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Submit
from django import forms
from django.utils import timezone

from core.forms import DatePicker

from .models import Ballot, BallotComplete


class BallotForm(forms.ModelForm):
    class Meta:
        model = Ballot
        fields = [
            "sender",
            "name",
            "type",
            "attachment",
            "description",
            "due_date",
            "voters",
        ]
        widgets = {
            "due_date": DatePicker(
                options={"format": "M/DD/YYYY"},
                attrs={"autocomplete": "off"},
            ),
        }

    def clean_due_date(self):
        due_date = self.cleaned_data["due_date"]
        # Voting closes on the due date, so a new ballot must not open closed.
        # Editing an old ballot (to fix a typo) stays allowed.
        if self.instance.pk is None and due_date < timezone.localdate():
            raise forms.ValidationError("The due date must be today or later. Voting closes on the due date.")
        return due_date


class BallotCompleteForm(forms.ModelForm):
    """The vote itself. "Incomplete" is a status, never a selectable motion."""

    motion = forms.ChoiceField(label="Motion", choices=BallotComplete.VOTE_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = BallotComplete
        fields = ["motion"]


class BallotListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "event-search-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Ballots',
            Row(
                InlineField("name"),
                Field("type"),
                Field("due_date"),
                Field("voters"),
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


class BallotUserListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "event-search-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Ballots',
            Row(
                InlineField("name"),
                Field("due_date"),
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


class BallotCompleteListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "event-search-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True

    def __init__(self, *args, show_results=True, **kwargs):
        super().__init__(*args, **kwargs)
        # Matches BallotCompleteFilter: only result viewers get the motion filter.
        vote_field = Field("motion") if show_results else Field("status")
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter Complete Ballots',
                Row(
                    Field("region"),
                    vote_field,
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
