from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from tempus_dominus.widgets import DatePicker
from .models import Initiation, Depledge, StatusChange
from users.models import User


class SetNoValidateField(forms.CharField):
    def validate(self, value):
        return


class InitDeplSelectForm(forms.Form):
    user = forms.ModelChoiceField(queryset=Initiation.objects.none(), disabled=True)
    state = forms.ChoiceField(choices=[('Initiate', 'Initiate'),
                                       ('Depledge', 'Depledge'),
                                       ('Defer', 'Defer')])


class InitDeplSelectFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        'user',
        'state',
    )


class InitiationForm(forms.ModelForm):
    user = SetNoValidateField(disabled=True)
    date_graduation = forms.DateField(
        label="Graduation Date",
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                          attrs={'autocomplete': 'off'},
                          ))
    date = forms.DateField(
        label="Initiation Date",
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                          attrs={'autocomplete': 'off'},
                          ))

    class Meta:
        model = Initiation
        fields = [
            'user', 'date',
            'date_graduation',
                  'roll', 'gpa', 'test_a',
                  'test_b', 'badge', 'guard']

    def clean_user(self):
        data = self.cleaned_data['user']
        user = User.objects.filter(name=data).first()
        return user.pk


InitiationFormSet = forms.formset_factory(InitiationForm, extra=0)


class InitiationFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    form_tag = False
    layout = Layout(
        'user',
        'date',
        'date_graduation',
        'roll',
        'gpa',
        'test_a',
        'test_b',
        'badge',
        'guard',
                )


class DepledgeForm(forms.ModelForm):
    user = SetNoValidateField(disabled=True)
    date = forms.DateField(
        label="Depledge Date",
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                                             attrs={'autocomplete': 'off'},
                                             ))

    class Meta:
        model = Depledge
        fields = [
            'user',
            'reason',
            'date'
                  ]

    def clean_user(self):
        data = self.cleaned_data['user']
        user = User.objects.filter(name=data).first()
        return user.pk


DepledgeFormSet = forms.formset_factory(DepledgeForm, extra=0)


class DepledgeFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    form_tag = False
    layout = Layout(
        'user',
        'reason',
        'date'
    )


class StatusChangeSelectForm(forms.Form):
    user = forms.ModelChoiceField(queryset=StatusChange.objects.none())
    state = forms.ChoiceField(choices=[x.value for x in StatusChange.REASONS])


class StatusChangeSelectFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        'user',
        'state',
    )


class GraduateForm(forms.ModelForm):
    user = SetNoValidateField(disabled=True)
    reason = SetNoValidateField(disabled=True)
    date_start = forms.DateField(
        label="Graduation Date",
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                          attrs={'autocomplete': 'off'},
                          ))
    email_personal = forms.EmailField()
    email_work = forms.EmailField()

    class Meta:
        model = StatusChange
        fields = [
            'user',
            'reason',  # Set selected
            'degree',
            'date_start',  # Graduation Date
            'employer',  # label=Employer/<br>School/Location
            'email_personal',  # get from user model PERSONAL<br>Email Address
            'email_work',
                  ]

    def clean_user(self):
        data = self.cleaned_data['user']
        user = User.objects.filter(name=data).first()
        return user


GraduateFormSet = forms.formset_factory(GraduateForm, extra=0)


class GraduateFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    form_tag = False
    layout = Layout(
        'user',
        'reason',  # Set selected
        'degree',
        'date_start',  # Graduation Date
        'employer',  # label=Employer/<br>School/Location
        'email_personal',  # get from user model PERSONAL<br>Email Address
        'email_work',
    )


class CSMTForm(forms.ModelForm):
    """
    For Coop, StudyAbroad, Military, Transfer Forms
    """
    user = SetNoValidateField(disabled=True)
    reason = SetNoValidateField(disabled=True)
    date_start = forms.DateField(
        label="Start Date",
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                          attrs={'autocomplete': 'off'},
                          ))
    date_end = forms.DateField(
        label="End Date",
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                          attrs={'autocomplete': 'off'},
                          ))
    class Meta:
        model = StatusChange
        fields = [
            'user',
            'reason',  # Set selected
            'employer',  # If Coop only
            'new_school',  # If transfer
            'date_start',
            'date_end',
            'miles',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reason = self.initial.get('reason', None)
        if reason == 'coop':
            self.fields['new_school'].widget = forms.HiddenInput()
        if reason == 'military':
            self.fields['miles'].widget.attrs['disabled'] = 'true'
            self.fields['miles'].required = False
            self.fields['employer'].widget.attrs['disabled'] = 'true'
            self.fields['employer'].required = False
            self.fields['new_school'].widget = forms.HiddenInput()
            self.fields['new_school'].required = False
        if reason == 'withdraw':
            self.fields['miles'].widget.attrs['disabled'] = 'true'
            self.fields['miles'].required = False
            self.fields['date_end'].widget.attrs['disabled'] = 'true'
            self.fields['date_end'].required = False
            self.fields['employer'].widget.attrs['disabled'] = 'true'
            self.fields['employer'].required = False
            self.fields['new_school'].widget = forms.HiddenInput()
            self.fields['new_school'].required = False
        if reason == 'transfer':
            self.fields['miles'].widget.attrs['disabled'] = 'true'
            self.fields['miles'].required = False
            self.fields['date_end'].widget.attrs['disabled'] = 'true'
            self.fields['date_end'].required = False
            self.fields['employer'].widget = forms.HiddenInput()
            self.fields['employer'].required = False

    def clean_user(self):
        data = self.cleaned_data['user']
        user = User.objects.filter(name=data).first()
        return user


CSMTFormSet = forms.formset_factory(CSMTForm, extra=0)


class CSMTFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    form_tag = False
    layout = Layout(
        'user',
        'reason',  # Set selected
        'employer',
        'new_school',  # If transfer
        'date_start',
        'date_end',
        'miles',
    )
