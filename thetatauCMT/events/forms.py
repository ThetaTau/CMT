from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from django import forms
from .models import Event, Picture


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

    def __init__(self, form=None, natoff=False):
        extra = []
        if natoff:
            extra = [
                InlineField("region"),
                InlineField("chapter"),
                InlineField("pictures"),
            ]
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter Events',
                Row(
                    InlineField("name"),
                    InlineField("date"),
                    InlineField("type"),
                    *extra,
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
        super().__init__(form=form)


class PictureForm(forms.ModelForm):
    image = forms.ImageField()

    class Meta:
        model = Picture
        fields = [
            "description",
            "image",
        ]


class EventForm(forms.ModelForm):
    """
    This is a Model From created to add help text to the create
    event form without changing database model. The Duration field
    is the only field that is updated.
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
            "virtual",
            "miles",
            "raised",
        ]

    # a clean method does not work b/c the chapter_id is not set in the form
