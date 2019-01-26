import datetime
from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, Button
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from core.models import BIENNIUM_YEARS
from chapters.models import Chapter, ChapterCurricula
from .models import UserAlterChapter, User, UserSemesterGPA


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
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type='submit',
                            css_class='btn-primary',),
                        Submit(
                            'cancel',
                            'Clear',
                            css_class='btn-primary'),
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
                        Column(InlineField('name__icontains')),
                        Column(InlineField('current_status')),
                        Column(InlineField('major__icontains')),
                        Column(InlineField('graduation_year__icontains')),
                        Column(InlineField('chapter')),
                        Column(FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Filter',
                                type='submit',
                                css_class='btn-primary'),
                            Submit(
                                'cancel',
                                'Clear',
                                css_class='btn-primary'),
                        )),
                        Column(InlineField('role')),
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


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['name', 'major', 'graduation_year', 'phone_number', 'address']


class UserGPAForm(forms.Form):
    user = forms.CharField(label="",
                           widget=forms.TextInput(
                               attrs={'readonly': 'readonly'}))
    gpa1 = forms.FloatField(label="", max_value=5.0, min_value=0)  # Fall 2018
    gpa2 = forms.FloatField(label="", max_value=5.0, min_value=0)  # Spring 2019
    gpa3 = forms.FloatField(label="", max_value=5.0, min_value=0)  # Fall 2019
    gpa4 = forms.FloatField(label="", max_value=5.0, min_value=0)  # Spring 2020

    def __init__(self, *args, **kwargs):
        hide_user = kwargs.pop('hide_user', False)
        super().__init__(*args, **kwargs)
        if hide_user:
            self.fields['user'].widget = forms.HiddenInput()

    def save(self):
        user_name = self.cleaned_data["user"]
        user = User.objects.filter(
            name=user_name, chapter__name=self.data['chapter']).last()
        for i in range(4):
            gpa = self.cleaned_data[f"gpa{i + 1}"]
            if gpa == 0:
                continue
            semester = 'sp' if i % 2 else 'fa'
            year = BIENNIUM_YEARS[i]
            try:
                obj = UserSemesterGPA.objects.get(
                    user=user,
                    year=year,
                    term=semester,
                )
            except UserSemesterGPA.DoesNotExist:
                obj = UserSemesterGPA(
                    user=user,
                    year=year,
                    term=semester,
                )
            obj.gpa = gpa
            obj.save()
