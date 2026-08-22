from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Submit
from django import forms

from core.forms import ComponentAddressField

from .models import Chapter


class ChapterForm(forms.ModelForm):
    address = ComponentAddressField(required=True)

    class Meta:
        model = Chapter
        fields = [
            "email",
            "website",
            "facebook",
            "instagram",
            "tiktok",
            "linkedin",
            "youtube",
            "twitter",
            "address",
            "address_line_2",
            "address_contact",
            "address_phone_number",
            "council",
            "house",
            "recognition",
            "recognition_url",
            "email_regent",
            "email_vice_regent",
            "email_scribe",
            "email_treasurer",
            "email_corresponding_secretary",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        optional_fields = {
            "email",
            "website",
            "facebook",
            "instagram",
            "tiktok",
            "linkedin",
            "youtube",
            "twitter",
            "address_line_2",
            "recognition_url",
            "email_regent",
            "email_vice_regent",
            "email_scribe",
            "email_treasurer",
            "email_corresponding_secretary",
        }
        for key in self.fields:
            if key not in optional_fields:
                self.fields[key].required = True


class ChapterFormHelper(FormHelper):
    form_method = "GET"
    form_id = "chapter-search-form"
    form_class = "form-inline"
    field_template = "bootstrap5/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Chapters',
            Row(
                InlineField("name__icontains"),
                InlineField("region"),
                InlineField("school__icontains"),
                InlineField("active"),
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
