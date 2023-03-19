from address.forms import AddressWidget
from betterforms.multiform import MultiModelForm
from crispy_forms.bootstrap import (
    FormActions,
    Field,
    InlineField,
    StrictButton,
    Accordion,
    AccordionGroup,
)
from crispy_forms.helper import FormHelper
from crispy_forms.layout import (
    Layout,
    Fieldset,
    Row,
    Submit,
    ButtonHolder,
    Column,
    HTML,
)
from dal import autocomplete, forward
from djmoney.forms.fields import MoneyField
from django import forms
from django.conf import settings
from django.utils import timezone
from tempus_dominus.widgets import DatePicker
from captcha.fields import ReCaptchaField
from captcha.widgets import ReCaptchaV3
from hcaptcha.fields import hCaptchaField
from upload_validator import FileTypeValidator
from chapters.forms import ChapterForm
from chapters.models import Chapter, ChapterCurricula
from core.address import fix_address
from core.forms import DuplicateAddressField, SchoolModelChoiceField
from core.models import CHAPTER_ROLES_CHOICES, NAT_OFFICERS_CHOICES
from users.models import User, UserRoleChange, UserDemographic
from .models import (
    Initiation,
    Bylaws,
    Depledge,
    StatusChange,
    RiskManagement,
    PledgeProgram,
    Audit,
    Pledge,
    HSEducation,
    PrematureAlumnus,
    Convention,
    OSM,
    DisciplinaryProcess,
    CollectionReferral,
    ResignationProcess,
    ReturnStudent,
)


class SetNoValidateField(forms.CharField):
    def validate(self, value):
        return


class UserSelectForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete", forward=(forward.Const("false", "chapter"),)
        ),
    )


class InitDeplSelectForm(forms.Form):
    user = forms.ModelChoiceField(queryset=Initiation.objects.none(), disabled=True)
    state = forms.ChoiceField(
        choices=[
            ("Initiate", "Initiate"),
            ("Depledge", "Depledge"),
            ("Defer", "Defer"),
            ("Roll", "Roll Book"),
        ]
    )


class InitDeplSelectFormHelper(FormHelper):
    template = "bootstrap4/table_inline_formset.html"
    form_show_errors = True
    help_text_inline = False
    error_text_inline = True
    html5_required = False
    layout = Layout(
        "user",
        "state",
    )


class InitiationForm(forms.ModelForm):
    user = SetNoValidateField(disabled=True)
    date_graduation = forms.DateField(
        label="Graduation Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    date = forms.DateField(
        label="Initiation Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = Initiation
        fields = [
            "user",
            "date",
            "date_graduation",
            "roll",
            "gpa",
            "test_a",
            "test_b",
            "badge",
        ]

    def clean_user(self):
        data = self.cleaned_data["user"]
        user = User.objects.filter(name=data, chapter__name=self.data["chapter"]).last()
        if user:
            return user.pk
        return ""

    def clean_roll(self):
        data = self.cleaned_data["roll"]
        chapter = Chapter.objects.get(name=self.data["chapter"])
        max_badge = chapter.next_badge_number()
        chapter_badge_numbers = chapter.members.values_list("badge_number", flat=True)
        if data in chapter_badge_numbers:
            raise forms.ValidationError(
                f"Badge number taken, chapter max badge number: {max_badge-1}"
            )
        return data


InitiationFormSet = forms.formset_factory(InitiationForm, extra=0)


class InitiationFormHelper(FormHelper):
    template = "bootstrap4/table_inline_formset.html"
    form_tag = False
    layout = Layout(
        "user",
        "date",
        "date_graduation",
        "roll",
        "gpa",
        "test_a",
        "test_b",
        "badge",
    )


class DepledgeForm(forms.ModelForm):
    user = SetNoValidateField(disabled=True)
    date = forms.DateField(
        label="Depledge Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
        help_text="Date can not be in the future",
    )
    meeting_date = forms.DateField(
        label="When was the meeting with the depledged PNM?",
        required=False,
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
        help_text="Date can not be in the future",
    )

    class Meta:
        model = Depledge
        fields = [
            "user",
            "reason",
            "reason_other",
            "date",
            "meeting_held",
            "meeting_date",
            "meeting_attend",
            "meeting_not",
            "informed",
            "concerns",
            "returned_items",
            "returned_other",
            "extra_notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["informed"].required = True
        self.fields["returned_items"].required = True

    def clean(self):
        super().clean()
        reason_other = self.cleaned_data.get("reason_other", "")
        if self.cleaned_data.get("reason") == "other" and reason_other == "":
            self.add_error(
                "reason_other",
                forms.ValidationError(
                    "You must submit the other reason for depledging"
                ),
            )
        meeting_held = self.cleaned_data.get("meeting_held")
        if not meeting_held:
            self.add_error(
                "meeting_held",
                forms.ValidationError("You must select if a meeting was held or not."),
            )
        elif "no" in meeting_held or "na" in meeting_held:
            meeting_not = self.cleaned_data.get("meeting_not", "")
            if meeting_not == "":
                self.add_error(
                    "meeting_not",
                    forms.ValidationError(
                        "You must submit a reason for no meeting with depledged."
                    ),
                )
        else:
            meeting_date = self.cleaned_data.get("meeting_date", "")
            meeting_attend = self.cleaned_data.get("meeting_attend", "")
            if meeting_date == "":
                self.add_error(
                    "meeting_date",
                    forms.ValidationError(
                        "You must submit meeting date for depledged meeting"
                    ),
                )
            if meeting_attend == "":
                self.add_error(
                    "meeting_attend",
                    forms.ValidationError(
                        "You must submit meeting attendance for depledged meeting"
                    ),
                )
        returned_other = self.cleaned_data.get("returned_other", "")
        returned_items = self.cleaned_data.get("returned_items")
        if not returned_items:
            self.add_error(
                "returned_items",
                forms.ValidationError("You must specify if items were returned."),
            )
        elif "other" in returned_items and returned_other == "":
            self.add_error(
                "returned_other",
                forms.ValidationError("You must submit the other returned items"),
            )

    def clean_user(self):
        data = self.cleaned_data["user"]
        user = User.objects.filter(name=data, chapter__name=self.data["chapter"]).last()
        if user:
            return user.pk
        return ""


DepledgeFormSet = forms.formset_factory(DepledgeForm, extra=0)


class DepledgeFormHelper(FormHelper):
    form_class = "form-inline"
    form_tag = False
    layout = Layout(
        Row(
            Column(
                "user",
            ),
            Column("date"),
            Column(Field("reason", css_class="reason-class")),
            Column(
                "reason_other",
            ),
        ),
        Row(
            Column(Field("meeting_held", css_class="meeting-held-class")),
            Column(
                "meeting_date",
            ),
            Column(
                "meeting_attend",
            ),
            Column(
                "meeting_not",
            ),
        ),
        "informed",
        "concerns",
        Row(
            Column(Field("returned_items", css_class="returned_items-class")),
            Column(
                "returned_other",
            ),
        ),
        "extra_notes",
    )


class StatusChangeSelectForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none())
    state = forms.ChoiceField(label="New Status")
    selected = forms.BooleanField(label="Remove", required=False)

    def __init__(self, *args, **kwargs):
        colony = kwargs.pop("colony", False)
        super().__init__(*args, **kwargs)
        exclude = ["covid"]
        if not colony:
            exclude.append("resignedCC")
        self.fields["state"].choices = [
            x.value for x in StatusChange.REASONS if x.name not in exclude
        ]


class StatusChangeSelectFormHelper(FormHelper):
    template = "bootstrap4/table_inline_formset.html"
    form_show_errors = True
    help_text_inline = False
    error_text_inline = True
    html5_required = False
    layout = Layout("user", "state", "selected")


class GraduateForm(forms.ModelForm):
    user = SetNoValidateField(disabled=True)
    reason = SetNoValidateField(disabled=True)
    date_start = forms.DateField(
        label="Graduation Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    email_personal = forms.EmailField()
    email_work = forms.EmailField(required=False)
    employer = forms.CharField(required=False)

    class Meta:
        model = StatusChange
        fields = [
            "user",
            "reason",  # Set selected
            "degree",
            "date_start",  # Graduation Date
            "employer",  # label=Employer/<br>School/Location
            "email_personal",  # get from user model PERSONAL<br>Email Address
            "email_work",
        ]

    def clean_user(self):
        data = self.cleaned_data["user"]
        user = User.objects.filter(name=data, chapter__name=self.data["chapter"]).last()
        if user:
            return user
        return ""


GraduateFormSet = forms.formset_factory(GraduateForm, extra=0)


class GraduateFormHelper(FormHelper):
    template = "bootstrap4/table_inline_formset.html"
    form_tag = False
    layout = Layout(
        "user",
        "reason",  # Set selected
        "degree",
        "date_start",  # Graduation Date
        "employer",  # label=Employer/<br>School/Location
        "email_personal",  # get from user model PERSONAL<br>Email Address
        "email_work",
    )


class CSMTForm(forms.ModelForm):
    """
    For Coop, StudyAbroad, Military, Transfer Forms
    """

    user = SetNoValidateField(disabled=True)
    reason = SetNoValidateField(disabled=True)
    date_start = forms.DateField(
        label="Start Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    date_end = forms.DateField(
        label="End Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = StatusChange
        fields = [
            "user",
            "reason",  # Set selected
            "employer",  # If Coop only
            "new_school",  # If transfer
            "date_start",
            "date_end",
            "miles",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reason = self.initial.get("reason", None)
        if reason == "coop":
            self.fields["new_school"].widget = forms.HiddenInput()
        if reason == "military":
            self.fields["miles"].widget.attrs["disabled"] = "true"
            self.fields["miles"].required = False
            self.fields["employer"].widget.attrs["disabled"] = "true"
            self.fields["employer"].required = False
            self.fields["new_school"].widget = forms.HiddenInput()
            self.fields["new_school"].required = False
        if reason == "withdraw" or reason == "resignedCC":
            self.fields["miles"].widget.attrs["disabled"] = "true"
            self.fields["miles"].required = False
            self.fields["date_end"].widget.attrs["disabled"] = "true"
            self.fields["date_end"].required = False
            self.fields["employer"].widget.attrs["disabled"] = "true"
            self.fields["employer"].required = False
            self.fields["new_school"].widget = forms.HiddenInput()
            self.fields["new_school"].required = False
        if reason == "transfer":
            self.fields["miles"].widget.attrs["disabled"] = "true"
            self.fields["miles"].required = False
            self.fields["date_end"].widget.attrs["disabled"] = "true"
            self.fields["date_end"].required = False
            self.fields["employer"].widget = forms.HiddenInput()
            self.fields["employer"].required = False
        if reason == "covid":
            self.fields["miles"].widget.attrs["disabled"] = "true"
            self.fields["miles"].required = False
            self.fields["date_end"].widget.attrs["disabled"] = "true"
            self.fields["date_end"].required = False
            self.fields["date_start"].widget.attrs["disabled"] = "true"
            self.fields["date_start"].required = False
            self.fields["employer"].widget.attrs["disabled"] = "true"
            self.fields["employer"].required = False
            self.fields["new_school"].widget = forms.HiddenInput()
            self.fields["new_school"].required = False

    def clean_user(self):
        data = self.cleaned_data["user"]
        user = User.objects.filter(name=data, chapter__name=self.data["chapter"]).last()
        if user:
            return user
        return ""

    def clean(self):
        super().clean()
        date_end = self.cleaned_data.get("date_end", "")
        date_start = self.cleaned_data.get("date_start", "")
        if date_end and date_start:
            if date_end < date_start:
                self.add_error(
                    "date_end",
                    forms.ValidationError(
                        "End date must be greater than the start date."
                    ),
                )
                raise forms.ValidationError(
                    "End date must be greater than the start date."
                )


CSMTFormSet = forms.formset_factory(CSMTForm, extra=0)


class CSMTFormHelper(FormHelper):
    template = "bootstrap4/table_inline_formset.html"
    form_tag = False
    layout = Layout(
        "user",
        "reason",  # Set selected
        "employer",
        "new_school",  # If transfer
        "date_start",
        "date_end",
        "miles",
    )


class RoleChangeNationalSelectForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete", forward=(forward.Const("false", "chapter"),)
        ),
        disabled=True,
    )
    role = forms.ChoiceField(
        choices=[("", "---------")] + NAT_OFFICERS_CHOICES, disabled=True
    )
    start = forms.DateField(
        initial=timezone.now().date(),
        label="Start Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
        disabled=True,
    )
    end = forms.DateField(
        initial=timezone.now().date() + timezone.timedelta(days=365),
        label="End Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
        disabled=True,
    )

    class Meta:
        model = UserRoleChange
        fields = [
            "user",
            "role",
            "start",
            "end",
        ]
        exclude = ["id"]


class RoleChangeSelectForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete", forward=(forward.Const("true", "chapter"),)
        ),
        disabled=True,
    )
    role = forms.ChoiceField(
        choices=[("", "---------")] + CHAPTER_ROLES_CHOICES, disabled=True
    )
    start = forms.DateField(
        initial=timezone.now().date(),
        label="Start Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
        disabled=True,
    )
    end = forms.DateField(
        initial=timezone.now().date() + timezone.timedelta(days=365),
        label="End Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
        disabled=True,
    )

    class Meta:
        model = UserRoleChange
        fields = [
            "user",
            "role",
            "start",
            "end",
        ]
        exclude = ["id"]


class RoleChangeSelectFormHelper(FormHelper):
    template = "bootstrap4/table_inline_formset.html"
    form_show_errors = True
    help_text_inline = False
    error_text_inline = True
    html5_required = False
    layout = Layout(
        "user",
        "role",
        "start",
        "end",
    )


class HSEducationListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "education-list-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter H&S Education Programs',
            Row(
                Field("region", label="Region"),
                Field("program_date"),
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


class BylawsListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "bylaws-list-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Bylaws',
            Row(
                Field("region", label="Region"),
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


class HSEducationForm(forms.ModelForm):
    report = forms.FileField(
        label="Program File",
        required=True,
        help_text="Only PDF format accepted",
        validators=[FileTypeValidator(allowed_types=["application/pdf"])],
    )

    class Meta:
        model = HSEducation
        fields = [
            "program_date",
            "category",
            "report",
            "title",
            "first_name",
            "last_name",
            "email",
            "phone_number",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].required = True


class BylawsForm(forms.ModelForm):
    bylaws = forms.FileField(
        label="Bylaws File",
        required=True,
        help_text="Only PDF format accepted",
        validators=[FileTypeValidator(allowed_types=["application/pdf"])],
    )

    class Meta:
        model = Bylaws
        fields = [
            "bylaws",
            "changes",
        ]


class ChapterInfoReportForm(MultiModelForm):
    form_classes = {
        "report": HSEducationForm,
        "info": ChapterForm,
    }


class RiskManagementForm(forms.ModelForm):
    alcohol = forms.BooleanField(label="I understand the Policy on Alcoholic Beverages")
    hosting = forms.BooleanField(label="I understand the Policy on Hosting an event")
    monitoring = forms.BooleanField(
        label="I understand the Policy on Organizing/Monitoring an event"
    )
    member = forms.BooleanField(
        label="I understand the Policy on Member Responsibilities"
    )
    officer = forms.BooleanField(
        label="I understand the Policy on Officer Responsibilities"
    )
    abusive = forms.BooleanField(label="I understand the Policy on Abusive Behavior")
    hazing = forms.BooleanField(label="I understand the Policy on Hazing")
    substances = forms.BooleanField(
        label="I understand the Policy on Controlled Substances"
    )
    high_risk = forms.BooleanField(label="I understand the Policy on High Risk Events")
    transportation = forms.BooleanField(
        label="I understand the Policy on Transportation"
    )
    property_management = forms.BooleanField(
        label="I understand the Policy on Property Management"
    )
    guns = forms.BooleanField(label="I understand the Policy on Gun Safety")
    trademark = forms.BooleanField(label="I understand the Trademark Policy")
    social = forms.BooleanField(label="I understand the Website & Social Media Policy")
    indemnification = forms.BooleanField(
        label="I understand the Indemnification, Authority, and Signatory Policy"
    )
    electronic_agreement = forms.BooleanField(label="I agree ")
    terms_agreement = forms.BooleanField(
        label="I accept the Electronic Terms of Service"
    )
    photo_release = forms.BooleanField(label="I accept the Photo and Image Release")
    arbitration = forms.BooleanField(label="I accept the Arbitration Agreement")
    fines = forms.BooleanField(label="I accept the Fines and Late Fees Schedule")
    dues = forms.BooleanField(label="I accept the Dues Agreement")
    agreement = forms.BooleanField(label="I agree")

    class Meta:
        model = RiskManagement
        fields = [
            "alcohol",
            "hosting",
            "monitoring",
            "member",
            "officer",
            "abusive",
            "hazing",
            "substances",
            "high_risk",
            "transportation",
            "property_management",
            "guns",
            "trademark",
            "social",
            "indemnification",
            "agreement",
            "electronic_agreement",
            "photo_release",
            "arbitration",
            "fines",
            "dues",
            "terms_agreement",
            "typed_name",
        ]


class PledgeProgramForm(forms.ModelForm):
    date_complete = forms.DateField(
        label="When do you anticipate completing new member education?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    date_initiation = forms.DateField(
        label="When do you plan to initiate your pledges?",
        help_text="Best estimated date is sufficient.",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    other_manual = forms.FileField(
        label="Other/Changes",
        required=False,
        help_text=(
            "If you are following a different program upload that full program. "
            "If you have made any changes to official program, "
            "upload ONLY THOSE CHANGES"
        ),
    )
    schedule = forms.FileField(
        help_text="Please upload a schedule of the PNM program process.",
        required=True,
    )
    test = forms.FileField(
        help_text="Please upload the test the PNMs take for your chapter. Please make sure to include the entire test including any chapter and national components.",
        required=True,
    )

    class Meta:
        model = PledgeProgram
        fields = [
            "remote",
            "weeks",
            "date_complete",
            "date_initiation",
            "manual",
            "other_manual",
            "schedule",
            "test",
        ]

    def clean(self):
        super().clean()
        other_manual = self.cleaned_data.get("other_manual", "")
        if self.cleaned_data.get("manual") == "other" and other_manual == "":
            self.add_error(
                "other_manual",
                forms.ValidationError(
                    "You must submit the other manual your chapter is "
                    "following if not one of the approved models."
                ),
            )


class AuditForm(forms.ModelForm):
    payment_plan = forms.TypedChoiceField(
        label="Does the chapter offer a Payment Plan for members?",
        coerce=lambda x: x == "True",
        choices=((False, "No"), (True, "Yes")),
    )
    cash_book = forms.TypedChoiceField(
        coerce=lambda x: x == "True", choices=((False, "No"), (True, "Yes"))
    )
    cash_register = forms.TypedChoiceField(
        coerce=lambda x: x == "True", choices=((False, "No"), (True, "Yes"))
    )
    member_account = forms.TypedChoiceField(
        coerce=lambda x: x == "True", choices=((False, "No"), (True, "Yes"))
    )
    debit_card = forms.TypedChoiceField(
        label="Does the chapter have a debit card used by members?",
        coerce=lambda x: x == "True",
        choices=((False, "No"), (True, "Yes")),
    )

    class Meta:
        model = Audit
        exclude = ["user", "term", "created", "year", "modified"]

    def clean(self):
        cleaned_data = super().clean()
        required_fields = [
            "cash_book_reviewed",
            "cash_register_reviewed",
            "member_account_reviewed",
            "agreement",
        ]
        for field in required_fields:
            value = cleaned_data.get(field)
            if not value:
                self.add_error(
                    field, f"{field.replace('_', ' ')} is required to be completed."
                )
        return self.cleaned_data


class AuditListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "audit-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Audits',
            Row(
                Field("chapter"),
                Field("user__chapter__region"),
                InlineField("modified"),
                Field("debit_card"),
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


class PledgeProgramFormHelper(FormHelper):
    form_method = "GET"
    form_id = "pledge_program-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            "",
            Row(
                Field("region"),
                Field("complete"),
                Field("year"),
                Field("term"),
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


class CompleteFormHelper(FormHelper):
    form_method = "GET"
    form_id = "pledge_program-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Forms',
            Row(
                Field("region"),
                Field("complete"),
                Field("year"),
                Field("term"),
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


class RiskListFormHelper(FormHelper):
    form_method = "GET"
    form_id = "risk-search-form"
    form_class = "form-inline"
    field_template = "bootstrap3/layout/inline_field.html"
    field_class = "col-xs-3"
    label_class = "col-xs-3"
    form_show_errors = True
    help_text_inline = False
    html5_required = True
    layout = Layout(
        Fieldset(
            '<i class="fas fa-search"></i> Filter Risk Forms',
            Row(
                Field("region", label="Region"),
                Field("term"),
                Field("year"),
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


class PledgeForm(forms.ModelForm):
    other_college_choice = forms.ChoiceField(
        label="Have you ever attended any other college?",
        choices=[("true", "Yes"), ("false", "No")],
        initial="false",
    )
    explain_expelled_org_choice = forms.ChoiceField(
        label="Have you ever been expelled from or placed under suspension by any organization?",
        choices=[("true", "Yes"), ("false", "No")],
        initial="false",
    )
    explain_expelled_college_choice = forms.ChoiceField(
        label="Have you ever been expelled from any college?",
        choices=[("true", "Yes"), ("false", "No")],
        initial="false",
    )
    explain_crime_choice = forms.ChoiceField(
        label="Have you ever been convicted of any crime?",
        choices=[("true", "Yes"), ("false", "No")],
        initial="false",
    )
    loyalty = forms.ChoiceField(
        label=Pledge.verbose_loyalty,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    not_honor = forms.ChoiceField(
        label=Pledge.verbose_not_honor,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    accountable = forms.ChoiceField(
        label=Pledge.verbose_accountable,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    life = forms.ChoiceField(
        label=Pledge.verbose_life,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    unlawful = forms.ChoiceField(
        label=Pledge.verbose_unlawful,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    unlawful_org = forms.ChoiceField(
        label=Pledge.verbose_unlawful_org,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    brotherhood = forms.ChoiceField(
        label=Pledge.verbose_brotherhood,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    engineering = forms.ChoiceField(
        label=Pledge.verbose_engineering,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    engineering_grad = forms.ChoiceField(
        label=Pledge.verbose_engineering_grad,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    payment = forms.ChoiceField(
        label=Pledge.verbose_payment,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    attendance = forms.ChoiceField(
        label=Pledge.verbose_attendance,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    harmless = forms.ChoiceField(
        label=Pledge.verbose_harmless,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    alumni = forms.ChoiceField(
        label=Pledge.verbose_alumni,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    honest = forms.ChoiceField(
        label=Pledge.verbose_honest,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )
    bill = forms.ChoiceField(
        label=Pledge.verbose_bill,
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
    )

    class Meta:
        model = Pledge
        exclude = ["user", "created", "modified"]


class PledgeDemographicsForm(forms.ModelForm):
    first_gen = forms.ChoiceField(
        label="Are you a first-generation college student?",
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
        required=True,
    )
    english = forms.ChoiceField(
        label="Is English your first language?",
        choices=[("", ""), (True, "Yes"), (False, "No")],
        initial="",
        required=True,
    )

    class Meta:
        model = UserDemographic
        exclude = ["user", "specific_ethnicity"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in [
                "gender_write",
                "sexual_write",
                "racial_write",
                "ability_write",
            ]:
                self.fields[field].required = True


class PledgeUserBase(forms.ModelForm):
    school_name = SchoolModelChoiceField(
        queryset=Chapter.objects.exclude(active=False).order_by("school")
    )
    birth_date = forms.DateField(
        label="Birth Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    address = DuplicateAddressField(widget=AddressWidget)
    email = forms.EmailField(
        label="Email Address", help_text="Non school email, does NOT end in .edu"
    )

    class Meta:
        model = User
        fields = [
            "title",
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
            "preferred_name",
            "nickname",
            "birth_date",
            "address",
            "email",
            "email_school",
            "major",
            "graduation_year",
            "phone_number",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field in ["nickname", "suffix"]:
                continue
            if field == "email_school":
                self.fields["email_school"].initial = ""
            if field not in ["middle_name", "preferred_name"]:
                self.fields[field].required = True
            else:
                self.fields[field].widget = forms.TextInput(
                    attrs={"placeholder": "If None, leave blank"}
                )
                if field == "middle_name":
                    self.fields[field].help_text = "If None, leave blank"

    def clean_address(self):
        address = self.cleaned_data["address"]
        if address.raw == "None" or address.raw == "":
            raise forms.ValidationError("Address should not be None or blank")
        if not address.locality:
            address = fix_address(address)
        if address is None:
            raise forms.ValidationError("Invalid Address")
        return address

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email.endswith(".edu"):
            raise forms.ValidationError(
                "No .edu email addresses allowed for personal email"
            )
        return email


class PledgeUser(PledgeUserBase):
    captcha = ReCaptchaField(label="", widget=ReCaptchaV3)
    if getattr(settings, "DEBUG", False):
        captcha.clean = lambda x: True


class PledgeUserAlt(PledgeUserBase):
    captcha = hCaptchaField()


class CrispyCompatableMultiModelForm(MultiModelForm):
    def __getitem__(self, key):
        if "-" in key:
            form, key = key.split("-")
            return self.forms[form][key]
        elif hasattr(self, key):
            return getattr(self, key)
        return self.forms[key]


class PledgeFormFull(CrispyCompatableMultiModelForm):
    form_classes = {
        "pledge": PledgeForm,
        "user": PledgeUser,
        "demographics": PledgeDemographicsForm,
    }

    def __init__(self, *args, **kwargs):
        alt_form = kwargs.get("alt_form", False)
        if alt_form:
            self.form_classes["user"] = PledgeUserAlt
        else:
            self.form_classes["user"] = PledgeUser
        if "alt_form" in kwargs:
            kwargs.pop("alt_form")
        super().__init__(*args, **kwargs)
        self.forms["user"].fields["major"].queryset = ChapterCurricula.objects.none()
        if "user-school_name" in self.forms["user"].data:
            try:
                chapter_id = int(self.data.get("user-school_name"))
                self.forms["user"].fields[
                    "major"
                ].queryset = ChapterCurricula.objects.filter(
                    chapter__pk=chapter_id
                ).order_by(
                    "major"
                )
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.forms["user"].instance.pk:
            self.forms["user"].fields["major"].queryset = self.forms[
                "user"
            ].instance.school_name.major_set.order_by("major")
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup(
                    "Personal Information",
                    Row(
                        Column(
                            "user-title",
                        ),
                        Column(
                            "user-first_name",
                        ),
                        Column(
                            "user-middle_name",
                        ),
                    ),
                    Row(
                        Column(
                            "user-last_name",
                        ),
                        Column(
                            "user-suffix",
                        ),
                    ),
                    "user-preferred_name",
                    "user-nickname",
                    "pledge-parent_name",
                    Row(
                        Column(
                            "user-email_school",
                        ),
                        Column(
                            "user-email",
                        ),
                    ),
                    Row(
                        Column(
                            "user-phone_number",
                        ),
                    ),
                    "user-address",
                    Row(
                        Column(
                            "user-birth_date",
                        ),
                        Column(
                            "pledge-birth_place",
                        ),
                    ),
                ),
                AccordionGroup(
                    "College & Degree Information",
                    Row(
                        Column(
                            "user-school_name",
                        ),
                        Column(
                            "user-major",
                        ),
                    ),
                    "user-graduation_year",
                    "pledge-other_degrees",
                    "pledge-relative_members",
                    "pledge-other_greeks",
                    "pledge-other_tech",
                    "pledge-other_frat",
                    "pledge-other_college_choice",
                    "pledge-other_college",
                    "pledge-explain_expelled_org_choice",
                    "pledge-explain_expelled_org",
                    "pledge-explain_expelled_college_choice",
                    "pledge-explain_expelled_college",
                    "pledge-explain_crime_choice",
                    "pledge-explain_crime",
                ),
                AccordionGroup(
                    "Demographics",
                    HTML(
                        "<h3>Why are we asking for these data?</h3>"
                        "<p>Theta Tau is committed to diversity, equity, "
                        "and inclusion. As part of that commitment, "
                        "we want to understand who our members are so that we "
                        "can gauge how diverse we are.</p>"
                    ),
                    HTML(
                        "<h3>What will Theta Tau do with these data?</h3>"
                        "<p>Our target right now is for our chapters to be at "
                        "least as diverse (in terms of gender and race "
                        "identities) as the population of engineers that they "
                        "draw from.  These data will be used to inform chapters "
                        "of how they compare.  These data will also be used to "
                        "study regional and national trends.</p>"
                        "<p>Theta Tau will not associate these data with "
                        "individual member records; e.g., "
                        "when a member is looked up in the database, "
                        "it will not say “John Doe, black gay male.” "
                        "These data will only be used and reviewed in the aggregate. "
                        "These data will also never be broken down to the "
                        "point where a casual observer would be able to "
                        "identify individual members from the data "
                        "(we will never share data about an individual pledge "
                        "class, or a very small chapter.)</p>"
                        "<p>We will never use these data to target "
                        "communications or programming advertisements to you.</p>"
                    ),
                    "demographics-gender",
                    "demographics-gender_write",
                    "demographics-sexual",
                    "demographics-sexual_write",
                    "demographics-racial",
                    "demographics-racial_write",
                    "demographics-ability",
                    "demographics-ability_write",
                    "demographics-first_gen",
                    "demographics-english",
                ),
                AccordionGroup(
                    "BILL OF RIGHTS",
                    HTML(
                        "<div id='bill'>Select your 'School Name' under 'College & Degree Information'</div>"
                    ),
                    "pledge-bill",
                ),
                AccordionGroup(
                    "Pause and Deliberate",
                    HTML(
                        "<h2>Please carefully read and answer each question below honestly</h2>"
                    ),
                    "pledge-loyalty",
                    "pledge-not_honor",
                    "pledge-accountable",
                    "pledge-life",
                    "pledge-unlawful",
                    "pledge-unlawful_org",
                    "pledge-brotherhood",
                    "pledge-engineering",
                    "pledge-engineering_grad",
                    "pledge-payment",
                    "pledge-attendance",
                    "pledge-harmless",
                    "pledge-alumni",
                    "pledge-honest",
                    "pledge-signature",
                ),
                Field(
                    "user-captcha",
                ),
                ButtonHolder(Submit("submit", "Submit", css_class="btn-primary")),
            ),
        )


class PrematureAlumnusForm(forms.ModelForm):
    CHOICES = [("", ""), (True, "True"), (False, "False")]
    good_standing = forms.ChoiceField(
        label=PrematureAlumnus.verbose_good_standing, choices=CHOICES, initial=""
    )
    financial = forms.ChoiceField(
        label=PrematureAlumnus.verbose_financial, choices=CHOICES, initial=""
    )
    semesters = forms.ChoiceField(
        label=PrematureAlumnus.verbose_semesters, choices=CHOICES, initial=""
    )
    lifestyle = forms.ChoiceField(
        label=PrematureAlumnus.verbose_lifestyle, choices=CHOICES, initial=""
    )
    consideration = forms.ChoiceField(
        label=PrematureAlumnus.verbose_consideration, choices=CHOICES, initial=""
    )
    vote = forms.ChoiceField(
        label=PrematureAlumnus.verbose_vote, choices=CHOICES, initial=""
    )
    user = forms.ModelChoiceField(
        label="Member requesting prealumn status",
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
    )
    form = forms.FileField(
        help_text="Only PDF format accepted",
        validators=[FileTypeValidator(allowed_types=["application/pdf"])],
    )

    class Meta:
        model = PrematureAlumnus
        fields = [
            "user",
            "form",
            "good_standing",
            "financial",
            "semesters",
            "lifestyle",
            "consideration",
            "prealumn_type",
            "vote",
        ]

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get("user")
        semesters = cleaned_data.get("semesters", False) == "True"
        initiation_date_min = timezone.now().date() - timezone.timedelta(days=30 * 6)
        # If initiation doesn't exist, then likely initiated plenty of time
        initiation_date = timezone.now().date() - timezone.timedelta(days=30 * 7)
        if hasattr(user, "initiation"):
            initiation_date = user.initiation.date
        if not semesters or initiation_date >= initiation_date_min:
            # initiation date > means that the date is newer then the minimum
            raise forms.ValidationError(
                f"{user} must have completed 6 months of initiation. "
                f"Reported initiation date is {initiation_date} "
                f"which is less than {initiation_date_min}. "
                f"Please reach out to the central office if you believe there is an error in this date."
            )
        return self.cleaned_data


class ConventionForm(forms.ModelForm):
    delegate = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
    )
    alternate = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
    )
    meeting_date = forms.DateField(
        label="Meeting Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = Convention
        fields = [
            "meeting_date",
            "delegate",
            "alternate",
        ]


class OSMForm(forms.ModelForm):
    nominate = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(forward.Const("true", "chapter"),),
        ),
    )
    meeting_date = forms.DateField(
        label="Meeting Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = OSM
        fields = [
            "meeting_date",
            "nominate",
            "selection_process",
        ]


class DisciplinaryForm1(forms.ModelForm):
    user = forms.ModelChoiceField(
        label="Name of Accused",
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
    )
    notify_date = forms.DateField(
        label="Accused first notified of charges on date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    charges_filed = forms.DateField(
        label="Charges filed by majority vote at a chapter meeting on date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    trial_date = forms.DateField(
        label="Trial scheduled for date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    notify_method = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=[x.value for x in DisciplinaryProcess.METHODS],
    )
    charging_letter = forms.FileField(
        help_text="Only PDF format accepted",
        validators=[FileTypeValidator(allowed_types=["application/pdf"])],
    )
    address = DuplicateAddressField(widget=AddressWidget)

    class Meta:
        model = DisciplinaryProcess
        fields = [
            "financial",
            "user",
            "address",
            "charges",
            "resolve",
            "advisor",
            "advisor_name",
            "faculty",
            "faculty_name",
            "charges_filed",
            "notify_date",
            "notify_method",
            "trial_date",
            "charging_letter",
        ]

    def clean(self):
        cleaned_data = super().clean()
        advisor = cleaned_data.get("advisor")
        faculty = cleaned_data.get("faculty")
        advisor_name = cleaned_data.get("advisor_name")
        faculty_name = cleaned_data.get("faculty_name")
        if advisor and advisor_name is None:
            raise forms.ValidationError("Please provide the alumni advisor's name")
        if faculty and faculty_name is None:
            raise forms.ValidationError(
                "Please provide the campus/faculty adviser name"
            )
        return cleaned_data

    def clean_address(self):
        address = self.cleaned_data["address"]
        if address.raw == "None" or address.raw == "":
            raise forms.ValidationError("Address should not be None or blank")
        if not address.locality:
            address = fix_address(address)
        if address is None:
            raise forms.ValidationError("Invalid Address")
        return address


class DisciplinaryForm2(forms.ModelForm):
    rescheduled_date = forms.DateField(
        label="When will the new trial be held?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    notify_results_date = forms.DateField(
        label="On what date was the member notified of the results of the trial?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    suspension_end = forms.DateField(
        label="If suspended, when will this member’s suspension end?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"},
            attrs={"autocomplete": "off"},
        ),
    )
    minutes = forms.FileField(
        help_text="Only PDF format accepted",
        validators=[FileTypeValidator(allowed_types=["application/pdf"])],
    )
    results_letter = forms.FileField(
        help_text="Only PDF format accepted",
        validators=[FileTypeValidator(allowed_types=["application/pdf"])],
    )

    class Meta:
        model = DisciplinaryProcess
        fields = [
            "take",
            "why_take",
            "rescheduled_date",
            "attend",
            "guilty",
            "notify_results",
            "notify_results_date",
            "punishment",
            "suspension_end",
            "punishment_other",
            "collect_items",
            "minutes",
            "results_letter",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field in ["punishment_other", "minutes", "results_letter", "why_take"]:
                continue
            self.fields[field].required = True

    def clean(self):
        cleaned_data = super().clean()
        take = cleaned_data.get("take")
        why_take = cleaned_data.get("why_take")
        minutes = cleaned_data.get("minutes")
        results_letter = cleaned_data.get("results_letter")
        if not take and not why_take:
            raise forms.ValidationError("A reason for not taking place is required")
        if take and (minutes is None or results_letter is None):
            raise forms.ValidationError("Both minutes and results letter are required")
        return cleaned_data


class CollectionReferralForm(forms.ModelForm):
    user = forms.ModelChoiceField(
        label="Indebted Member",
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
    )
    balance_due = MoneyField(
        currency_widget=forms.HiddenInput(), default_currency="USD"
    )
    ledger_sheet = forms.FileField(
        help_text="Only PDF format accepted",
        validators=[FileTypeValidator(allowed_types=["application/pdf"])],
    )

    class Meta:
        model = CollectionReferral
        fields = [
            "user",
            "balance_due",
            "ledger_sheet",
        ]


class ResignationForm(forms.ModelForm):
    letter = forms.FileField(
        help_text="Only PDF format accepted",
        validators=[FileTypeValidator(allowed_types=["application/pdf"])],
    )

    class Meta:
        model = ResignationProcess
        fields = [
            "letter",
            "resign",
            "secrets",
            "expel",
            "return_evidence",
            "obligation",
            "fee",
            "signature",
        ]


class ReturnStudentForm(forms.ModelForm):
    CHOICES = [("", ""), (True, "True"), (False, "False")]
    financial = forms.ChoiceField(
        label=ReturnStudent.verbose_financial, choices=CHOICES, initial=""
    )
    debt = forms.ChoiceField(
        label=ReturnStudent.verbose_debt, choices=CHOICES, initial=""
    )
    vote = forms.ChoiceField(
        label=ReturnStudent.verbose_vote, choices=CHOICES, initial=""
    )
    user = forms.ModelChoiceField(
        label="Member requesting return",
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "alumni"),
            ),
        ),
    )

    class Meta:
        model = ReturnStudent
        fields = [
            "user",
            "reason",
            "financial",
            "debt",
            "vote",
        ]

    def clean_user(self):
        user = self.cleaned_data["user"]
        prealumn = user.prealumn_form.all()
        if prealumn:
            raise forms.ValidationError(
                f"{user} has a prealumn form filed. "
                f"They must email the central office "
                f"to resume student member status."
            )
        else:
            return user
