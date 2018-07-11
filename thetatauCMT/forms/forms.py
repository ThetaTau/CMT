from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout
from tempus_dominus.widgets import DatePicker
from .models import Initiation


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
    user = forms.ModelChoiceField(queryset=[], disabled=True)
    date_graduation = forms.DateField(widget=DatePicker(
                                      options={"format": "M/YYYY",}
                                      ))

    class Meta:
        model = Initiation
        fields = [
            'user',
            'date_graduation',
                  'roll', 'gpa', 'test_a',
                  'test_b', 'badge', 'guard']


class InitiationFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    # label_class = 'col-lg-1'
    # field_class = 'col-lg-9'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
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
