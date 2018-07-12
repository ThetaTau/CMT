from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from tempus_dominus.widgets import DatePicker
from .models import Initiation, Depledge
from users.models import User


class SetUserField(forms.CharField):
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
    user = SetUserField(disabled=True)  # forms.ModelChoiceField(queryset=Initiation.objects.none(), disabled=True)
    date_graduation = forms.DateField(
        # input_formats=["%m/%Y"],
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                          attrs={'autocomplete': 'off'},
                          ))

    class Meta:
        model = Initiation
        fields = [
            'user',
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
    # label_class = 'col-lg-1'
    # field_class = 'col-lg-9'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    form_tag = False
    layout = Layout(
        'user',
        'date_graduation',
        'roll',
        'gpa',
        'test_a',
        'test_b',
        'badge',
        'guard',
                )


class DepledgeForm(forms.ModelForm):
    user = SetUserField(disabled=True)  # forms.ModelChoiceField(queryset=Depledge.objects.none(), disabled=True)
    date = forms.DateField(widget=DatePicker(options={"format": "M/DD/YYYY"},
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
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    form_tag = False
    layout = Layout(
        'user',
        'reason',
        'date'
    )
