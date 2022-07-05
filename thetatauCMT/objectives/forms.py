from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Layout,
    Fieldset,
    Row,
    Submit,
    Column,
)
from crispy_forms.bootstrap import (
    FormActions,
    Field,
    InlineField,
    StrictButton,
)
from tempus_dominus.widgets import DatePicker
from django import forms
from dal import autocomplete, forward
from users.models import User
from .models import Objective, Action


class ObjectiveListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "objective-search-form"
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
            ]
        self.layout = Layout(
            Fieldset(
                '<i class="fas fa-search"></i> Filter Goals',
                Row(
                    InlineField("title"),
                    InlineField("complete"),
                    InlineField("date"),
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


class ObjectiveForm(forms.ModelForm):
    owner = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
    )
    date = forms.DateField(
        label="When do you want the goal to be accomplished by?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = Objective
        fields = [
            "owner",
            "title",
            "date",
            "complete",
            "description",
        ]

    def __init__(self, *args, **kwargs):
        owner = kwargs.get("owner", False)
        if "owner" in kwargs:
            kwargs.pop("owner")
        super().__init__(*args, **kwargs)
        if not owner:
            for nam, field in self.fields.items():
                field.disabled = True


class ActionForm(forms.ModelForm):
    owner = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
    )
    date = forms.DateField(
        label="When do you want the action to be accomplished by?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = Action
        fields = [
            "owner",
            "date",
            "complete",
            "description",
        ]
