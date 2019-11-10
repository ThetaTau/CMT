from django import forms
from django.utils import timezone
from dal import autocomplete, forward
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Submit
from crispy_forms.bootstrap import FormActions, Field, InlineField, StrictButton
from tempus_dominus.widgets import DatePicker
from .models import Initiation, Depledge, StatusChange, RiskManagement,\
    PledgeProgram, Audit
from core.models import CHAPTER_ROLES_CHOICES
from users.models import User, UserRoleChange
from regions.models import Region
from core.models import CHAPTER_OFFICER, COMMITTEE_CHAIR


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
    error_text_inline = True
    html5_required = False
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
        user = User.objects.filter(
            name=data, chapter__name=self.data['chapter']).last()
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
        user = User.objects.filter(
            name=data, chapter__name=self.data['chapter']).last()
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
    user = forms.ModelChoiceField(queryset=User.objects.none())
    state = forms.ChoiceField(choices=[x.value for x in StatusChange.REASONS])
    selected = forms.BooleanField(label="Remove", required=False)


class StatusChangeSelectFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    form_show_errors = True
    help_text_inline = False
    error_text_inline = True
    html5_required = False
    layout = Layout(
        'user',
        'state',
        'selected'
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
    email_work = forms.EmailField(required=False)
    employer = forms.CharField(required=False)

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
        user = User.objects.filter(
            name=data, chapter__name=self.data['chapter']).last()
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
        user = User.objects.filter(
            name=data, chapter__name=self.data['chapter']).last()
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


class RoleChangeSelectForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url='users:autocomplete',
            forward=(forward.Const('true', 'chapter'),)
            )
        )
    start = forms.DateField(
        initial=timezone.now(),
        label="Start Date",
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                          attrs={'autocomplete': 'off'},
                          ))
    end = forms.DateField(
        initial=timezone.now() + timezone.timedelta(days=365),
        label="End Date",
        widget=DatePicker(options={"format": "M/DD/YYYY"},
                          attrs={'autocomplete': 'off'},
                          ))

    class Meta:
        model = UserRoleChange
        fields = [
            'user',
            'role',
            'start',
            'end',
        ]
        exclude = ['id']


class RoleChangeSelectFormHelper(FormHelper):
    template = 'bootstrap4/table_inline_formset.html'
    form_show_errors = True
    help_text_inline = False
    error_text_inline = True
    html5_required = False
    layout = Layout(
        'user',
        'role',
        'start',
        'end',
    )


class RiskManagementForm(forms.ModelForm):
    alcohol = forms.BooleanField(label="I understand the Policy on Alcoholic Beverages")
    hosting = forms.BooleanField(label="I understand the Policy on Hosting an event")
    monitoring = forms.BooleanField(label="I understand the Policy on Organizing/Monitoring an event")
    member = forms.BooleanField(label="I understand the Policy on Member Responsibilities")
    officer = forms.BooleanField(label="I understand the Policy on Officer Responsibilities")
    abusive = forms.BooleanField(label="I understand the Policy on Abusive Behavior")
    hazing = forms.BooleanField(label="I understand the Policy on Hazing")
    substances = forms.BooleanField(label="I understand the Policy on Controlled Substances")
    high_risk = forms.BooleanField(label="I understand the Policy on High Risk Events")
    transportation = forms.BooleanField(label="I understand the Policy on Transportation")
    property_management = forms.BooleanField(label="I understand the Policy on Property Management")
    guns = forms.BooleanField(label="I understand the Policy on Gun Safety")
    trademark = forms.BooleanField(label="I understand the Trademark Policy")
    social = forms.BooleanField(label="I understand the Website & Social Media Policy")
    indemnification = forms.BooleanField(label="I understand the Indemnification, Authority, and Signatory Policy")
    electronic_agreement = forms.BooleanField(label="I agree ")
    terms_agreement = forms.BooleanField(label="I accept the Electronic Terms of Service")
    agreement = forms.BooleanField(label="I agree")

    class Meta:
        model = RiskManagement
        fields = [
            'alcohol',
            'hosting',
            'monitoring',
            'member',
            'officer',
            'abusive',
            'hazing',
            'substances',
            'high_risk',
            'transportation',
            'property_management',
            'guns',
            'trademark',
            'social',
            'indemnification',
            'agreement',
            'electronic_agreement',
            'terms_agreement',
            'typed_name',
        ]


class PledgeProgramForm(forms.ModelForm):
    class Meta:
        model = PledgeProgram
        fields = [
            'manual', 'other_manual'
        ]

    def clean_other_manual(self):
        other_manual = self.data.get('other_manual', '')
        other_manual_cleaned = self.cleaned_data.get('other_manual', '')
        if (self.cleaned_data.get('manual') == 'other' and
            other_manual == '' and other_manual_cleaned == ''):
                    raise forms.ValidationError(
                        'You must submit the other manual your chapter is '
                        'following if not one of the approved models.'
                    )
        if other_manual == '' and other_manual_cleaned != '':
            other_manual = other_manual_cleaned
        return other_manual


class AuditForm(forms.ModelForm):
    payment_plan = forms.TypedChoiceField(
        label="Does the chapter offer a Payment Plan for members?",
        coerce=lambda x: x == 'True', choices=((False, 'No'), (True, 'Yes')))
    cash_book = forms.TypedChoiceField(
        coerce=lambda x: x == 'True', choices=((False, 'No'), (True, 'Yes')))
    cash_register = forms.TypedChoiceField(
        coerce=lambda x: x == 'True', choices=((False, 'No'), (True, 'Yes')))
    member_account = forms.TypedChoiceField(
        coerce=lambda x: x == 'True', choices=((False, 'No'), (True, 'Yes')))
    debit_card = forms.TypedChoiceField(
        label="Does the chapter have a debit card used by members?",
        coerce=lambda x: x == 'True', choices=((False, 'No'), (True, 'Yes')))

    class Meta:
        model = Audit
        exclude = ['user', 'term', 'created', 'year', 'modified']

    def clean(self):
        cleaned_data = super().clean()
        required_fields = ['cash_book_reviewed', 'cash_register_reviewed',
                           'member_account_reviewed', 'agreement']
        for field in required_fields:
            value = cleaned_data.get(field)
            if not value:
                self.add_error(
                    field,
                    f"{field.replace('_', ' ')} is required to be completed.")
        return self.cleaned_data


class AuditListFormHelper(FormHelper):
    form_method = 'GET'
    form_id = 'audit-search-form'
    form_class = 'form-inline'
    field_template = 'bootstrap3/layout/inline_field.html'
    field_class = 'col-xs-3'
    label_class = 'col-xs-3'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
                Fieldset(
                    '<i class="fas fa-search"></i> Filter Audits',
                    Row(
                        Field('user__chapter'),
                        Field('user__chapter__region'),
                        InlineField('modified'),
                        Field('debit_card'),
                        FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Filter',
                                type='submit',
                                css_class='btn-primary',),
                            Submit(
                                'cancel',
                                'Clear',
                                css_class='btn-primary'),
                        )
                    )
                ),
    )


class PledgeProgramFormHelper(FormHelper):
    form_method = 'GET'
    form_id = 'pledge_program-search-form'
    form_class = 'form-inline'
    field_template = 'bootstrap3/layout/inline_field.html'
    field_class = 'col-xs-3'
    label_class = 'col-xs-3'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
                Fieldset(
                    '<i class="fas fa-search"></i> Filter Pledge Programs',
                    Row(
                        Field('region'),
                        Field('complete'),
                        Field('year'),
                        Field('term'),
                        Field('manual'),
                        FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Filter',
                                type='submit',
                                css_class='btn-primary',),
                            Submit(
                                'cancel',
                                'Clear',
                                css_class='btn-primary'),
                        )
                    )
                ),
    )


class RiskListFormHelper(FormHelper):
    form_method = 'GET'
    form_id = 'risk-search-form'
    form_class = 'form-inline'
    field_template = 'bootstrap3/layout/inline_field.html'
    field_class = 'col-xs-3'
    label_class = 'col-xs-3'
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
                Fieldset(
                    '<i class="fas fa-search"></i> Filter Risk Forms',
                    Row(
                        Field('region', label='Region'),
                        Field('year'),
                        Field('all_complete_status', label='Status All Complete'),
                        FormActions(
                            StrictButton(
                                '<i class="fa fa-search"></i> Filter',
                                type='submit',
                                css_class='btn-primary',),
                            Submit(
                                'cancel',
                                'Clear',
                                css_class='btn-primary'),
                        )
                    )
                ),
    )


class RiskListFilter(forms.Form):
    helper = RiskListFormHelper
    year = forms.ChoiceField(choices=[(2019, '2019'), (2018, '2018')])
    all_complete_status = forms.ChoiceField(
        choices=[(0, 'All'), (1, 'Complete'), (2, 'Incomplete')])
    region = forms.ChoiceField(required=False,
                               choices=Region.region_choices())
