from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit, Button
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from chapters.models import Chapter
from .models import UserAlterChapter


class UserListFormHelper(FormHelper):
    form_method = 'GET'
    form_id = 'user-search-form'
    form_class = 'form-inline'
    field_template = 'bootstrap3/layout/inline_field.html'
    field_class = 'col-xs-3'
    label_class = 'col-xs-3'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
                Fieldset(
                    '<i class="fas fa-search"></i> Filter Members',
                    Row(
                        InlineField('name__icontains'),
                        InlineField('current_status'),
                        InlineField('major__icontains'),
                        InlineField('graduation_year__icontains'),
                        FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Filter',
                                type='submit',
                                css_class='btn-primary',
                                style='margin-top:10px;')
                        )
                    )
                ),
    )


class UserRoleListFormHelper(FormHelper):
    form_method = 'GET'
    form_id = 'user-search-form'
    form_class = 'form-inline'
    field_template = 'bootstrap3/layout/inline_field.html'
    field_class = 'col-xs-3'
    label_class = 'col-xs-3'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
                Fieldset(
                    '<i class="fas fa-search"></i> Filter Members',
                    Row(
                        InlineField('name__icontains'),
                        InlineField('current_status'),
                        InlineField('major__icontains'),
                        InlineField('graduation_year__icontains'),
                        InlineField('chapter'),
                        FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Filter',
                                type='submit',
                                css_class='btn-primary'),
                            Submit(
                                'cancel',
                                'Clear',
                                css_class='btn-primary'),
                        ),
                        InlineField('role'),
                    )
                ),
    )


class UserLookupForm(forms.Form):
    university = forms.ChoiceField(choices=Chapter.schools())
    badge_number = forms.IntegerField()


class UserAlterForm(forms.ModelForm):
    class Meta:
        model = UserAlterChapter
        fields = ['chapter']
