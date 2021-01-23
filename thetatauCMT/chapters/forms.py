from django import forms
from address.forms import AddressWidget
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from .models import Chapter
from core.address import fix_address
from core.forms import DuplicateAddressField


class ChapterForm(forms.ModelForm):
    address = DuplicateAddressField(widget=AddressWidget)

    class Meta:
        model = Chapter
        fields = [
            "email",
            "website",
            "facebook",
            "address",
            "council",
            "recognition",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in self.fields:
            self.fields[key].required = True

    def clean_address(self):
        address = self.cleaned_data["address"]
        if address.raw == "None" or address.raw == "":
            raise forms.ValidationError("Address should not be None or blank")
        if not address.locality:
            address = fix_address(address)
        if address is None:
            raise forms.ValidationError("Invalid Address")
        return address


class ChapterFormHelper(FormHelper):
    form_method = "GET"
    form_id = "chapter-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
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
