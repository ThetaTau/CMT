import datetime
from django import forms
from django.utils import timezone
from address.forms import AddressField
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Submit, Button
from crispy_forms.bootstrap import FormActions, InlineField, StrictButton
from tempus_dominus.widgets import DatePicker
from core.models import BIENNIUM_YEARS
from chapters.models import Chapter, ChapterCurricula
from .models import (
    UserAlter,
    User,
    UserSemesterGPA,
    UserSemesterServiceHours,
    UserOrgParticipate,
)


class UserListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "user-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Members',
            Row(
                InlineField("name__icontains"),
                InlineField("major__icontains"),
                InlineField("graduation_year__icontains"),
                FormActions(
                    StrictButton(
                        '<i class="fa fa-search"></i> Filter',
                        type="submit",
                        css_class="btn-primary",
                    ),
                    Submit("cancel", "Clear", css_class="btn-primary"),
                    StrictButton(
                        '<i class="fa fa-search"></i> Download CSV',
                        type="submit",
                        value="Download CSV",
                        name="csv",
                        css_class="btn-secondary",
                    ),
                ),
            ),
            Row(InlineField("current_status"),),
        ),
    )


class UserRoleListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "user-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Members',
            Row(
                Column(InlineField("name__icontains")),
                Column(InlineField("current_status")),
                Column(InlineField("major__icontains")),
                Column(InlineField("graduation_year__icontains")),
                Column(InlineField("region")),
                Column(InlineField("chapter")),
                Column(
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    )
                ),
                Column(InlineField("role")),
            ),
        ),
    )


class AdvisorListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "user-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Advisors',
            Row(
                Column(InlineField("name__icontains")),
                Column(InlineField("region")),
                Column(InlineField("chapter")),
                Column(
                    FormActions(
                        StrictButton(
                            '<i class="fa fa-search"></i> Filter',
                            type="submit",
                            css_class="btn-primary",
                        ),
                        Submit("cancel", "Clear", css_class="btn-primary"),
                    )
                ),
            ),
        ),
    )


class UserLookupForm(forms.Form):
    university = forms.ChoiceField(choices=Chapter.schools())
    badge_number = forms.IntegerField()


class UserAlterForm(forms.ModelForm):
    role = forms.ChoiceField(choices=UserAlter.ROLES, required=False)

    class Meta:
        model = UserAlter
        fields = ["chapter", "role"]


class UserForm(forms.ModelForm):
    address = AddressField()

    class Meta:
        model = User
        fields = ["major", "graduation_year", "phone_number", "address"]


class UserGPAForm(forms.Form):
    user = forms.CharField(
        label="", widget=forms.TextInput(attrs={"readonly": "readonly"})
    )
    gpa1 = forms.FloatField(label="", max_value=5.0, min_value=0)  # Fall 2018
    gpa2 = forms.FloatField(label="", max_value=5.0, min_value=0)  # Spring 2019
    gpa3 = forms.FloatField(label="", max_value=5.0, min_value=0)  # Fall 2019
    gpa4 = forms.FloatField(label="", max_value=5.0, min_value=0)  # Spring 2020

    def __init__(self, *args, **kwargs):
        hide_user = kwargs.pop("hide_user", False)
        super().__init__(*args, **kwargs)
        if hide_user:
            self.fields["user"].widget = forms.HiddenInput()

    def save(self):
        user_name = self.cleaned_data["user"]
        user = User.objects.filter(
            name=user_name, chapter__name=self.data["chapter"]
        ).last()
        for i in range(4):
            gpa = self.cleaned_data[f"gpa{i + 1}"]
            if gpa == 0:
                continue
            semester = "sp" if i % 2 else "fa"
            year = BIENNIUM_YEARS[i]
            try:
                obj = UserSemesterGPA.objects.get(user=user, year=year, term=semester,)
            except UserSemesterGPA.DoesNotExist:
                obj = UserSemesterGPA(user=user, year=year, term=semester,)
            obj.gpa = gpa
            obj.save()


class UserServiceForm(forms.Form):
    user = forms.CharField(
        label="", widget=forms.TextInput(attrs={"readonly": "readonly"})
    )
    service1 = forms.FloatField(label="", min_value=0)  # Fall 2018
    service2 = forms.FloatField(label="", min_value=0)  # Spring 2019
    service3 = forms.FloatField(label="", min_value=0)  # Fall 2019
    service4 = forms.FloatField(label="", min_value=0)  # Spring 2020

    def __init__(self, *args, **kwargs):
        hide_user = kwargs.pop("hide_user", False)
        super().__init__(*args, **kwargs)
        if hide_user:
            self.fields["user"].widget = forms.HiddenInput()

    def save(self):
        user_name = self.cleaned_data["user"]
        user = User.objects.filter(
            name=user_name, chapter__name=self.data["chapter"]
        ).last()
        for i in range(4):
            service = self.cleaned_data[f"service{i + 1}"]
            if service == 0:
                continue
            semester = "sp" if i % 2 else "fa"
            year = BIENNIUM_YEARS[i]
            try:
                obj = UserSemesterServiceHours.objects.get(
                    user=user, year=year, term=semester,
                )
            except UserSemesterServiceHours.DoesNotExist:
                obj = UserSemesterServiceHours(user=user, year=year, term=semester,)
            obj.service_hours = service
            obj.save()


class UserOrgForm(forms.ModelForm):
    user = forms.ModelChoiceField(queryset=User.objects.none())
    start = forms.DateField(
        initial=timezone.now(),
        label="Start Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    end = forms.DateField(
        initial=timezone.now() + timezone.timedelta(days=365),
        label="End Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    officer = forms.TypedChoiceField(
        coerce=lambda x: x == "True", choices=((False, "No"), (True, "Yes"))
    )

    class Meta:
        model = UserOrgParticipate
        fields = ["user", "org_name", "type", "officer", "start", "end"]

    def __init__(self, *args, **kwargs):
        hide_user = kwargs.pop("hide_user", False)
        super().__init__(*args, **kwargs)
        if hide_user:
            self.fields["user"].widget = forms.HiddenInput()


class ExternalUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "title",
            "phone_number",
            "email",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in self.fields:
            self.fields[key].required = True
