from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Layout,
    Fieldset,
    Row,
    Submit,
)
from crispy_forms.bootstrap import (
    FormActions,
    InlineField,
    StrictButton,
)


class TrainingListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "training-search-form"
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
                '<i class="fas fa-search"></i> Filter Trainings',
                Row(
                    InlineField("course_title"),
                    InlineField("completed"),
                    InlineField("completed_time"),
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


class UserAdminTrainingForm(forms.Form):
    _selected_action = forms.CharField(widget=forms.MultipleHiddenInput)
    extra_group = forms.ChoiceField(label="Extra Group")
    new_group = forms.CharField(label="New Group Not Above", required=False)

    def __init__(self, extra_groups, *args, **kwargs):
        extra_groups.append(("new_group", "***NEW GROUP***"))
        self.base_fields["extra_group"].choices = extra_groups
        super().__init__(*args, **kwargs)

    def clean_new_group(self):
        new_group = self.cleaned_data["new_group"]
        new_group_short = new_group[0:8]
        existing_ids = [choice[0] for choice in self.base_fields["extra_group"].choices]
        if new_group_short in existing_ids:
            raise forms.ValidationError(
                f"The new group id is not unique: {new_group_short}. "
                f"The first 8 characters of the group name are used to identify it, "
                f"please pick something unique"
            )
        return new_group

    def clean(self):
        super().clean()
        new_group = self.cleaned_data.get("new_group", "")
        extra_group = self.cleaned_data.get("extra_group")
        if extra_group == "new_group" and new_group == "":
            self.add_error(
                "new_group",
                forms.ValidationError(
                    "You must set a new group name when ***NEW GROUP*** is selected above"
                ),
            )
        elif extra_group == "new_group" and new_group:
            self.cleaned_data["extra_group"] = new_group
