from betterforms.multiform import MultiModelForm
from crispy_forms.bootstrap import (
    FormActions,
    Field,
    InlineField,
    StrictButton,
    InlineRadios,
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
from django import forms
from django.utils import timezone
from tempus_dominus.widgets import DatePicker

from chapters.forms import ChapterForm
from chapters.models import Chapter, ChapterCurricula
from core.models import CHAPTER_ROLES_CHOICES, NAT_OFFICERS_CHOICES
from regions.models import Region
from users.models import User, UserRoleChange
from .models import (
    Initiation,
    Depledge,
    StatusChange,
    RiskManagement,
    PledgeProgram,
    Audit,
    Pledge,
    ChapterReport,
    PrematureAlumnus,
    Convention,
    OSM,
    DisciplinaryProcess,
)


class SetNoValidateField(forms.CharField):
    def validate(self, value):
        return


class InitDeplSelectForm(forms.Form):
    user = forms.ModelChoiceField(queryset=Initiation.objects.none(), disabled=True)
    state = forms.ChoiceField(
        choices=[("Initiate", "Initiate"), ("Depledge", "Depledge"), ("Defer", "Defer")]
    )


class InitDeplSelectFormHelper(FormHelper):
    template = "bootstrap4/table_inline_formset.html"
    form_show_errors = True
    help_text_inline = False
    error_text_inline = True
    html5_required = False
    layout = Layout("user", "state",)


class InitiationForm(forms.ModelForm):
    user = SetNoValidateField(disabled=True)
    date_graduation = forms.DateField(
        label="Graduation Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    date = forms.DateField(
        label="Initiation Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
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
            "guard",
        ]

    def clean_user(self):
        data = self.cleaned_data["user"]
        user = User.objects.filter(name=data, chapter__name=self.data["chapter"]).last()
        return user.pk


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
        "guard",
    )


class DepledgeForm(forms.ModelForm):
    user = SetNoValidateField(disabled=True)
    date = forms.DateField(
        label="Depledge Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = Depledge
        fields = ["user", "reason", "date"]

    def clean_user(self):
        data = self.cleaned_data["user"]
        user = User.objects.filter(name=data, chapter__name=self.data["chapter"]).last()
        return user.pk


DepledgeFormSet = forms.formset_factory(DepledgeForm, extra=0)


class DepledgeFormHelper(FormHelper):
    template = "bootstrap4/table_inline_formset.html"
    form_tag = False
    layout = Layout("user", "reason", "date")


class StatusChangeSelectForm(forms.Form):
    user = forms.ModelChoiceField(queryset=User.objects.none())
    state = forms.ChoiceField(choices=[x.value for x in StatusChange.REASONS])
    selected = forms.BooleanField(label="Remove", required=False)


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
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
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
        return user


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
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    date_end = forms.DateField(
        label="End Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
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
        if reason == "withdraw":
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

    def clean_user(self):
        data = self.cleaned_data["user"]
        user = User.objects.filter(name=data, chapter__name=self.data["chapter"]).last()
        return user


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
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
        disabled=True,
    )
    end = forms.DateField(
        initial=timezone.now().date() + timezone.timedelta(days=365),
        label="End Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
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
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
        disabled=True,
    )
    end = forms.DateField(
        initial=timezone.now().date() + timezone.timedelta(days=365),
        label="End Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
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
    layout = Layout("user", "role", "start", "end",)


class ChapterReportForm(forms.ModelForm):
    class Meta:
        model = ChapterReport
        fields = [
            "report",
        ]


class ChapterInfoReportForm(MultiModelForm):
    form_classes = {
        "report": ChapterReportForm,
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
            "dues",
            "terms_agreement",
            "typed_name",
        ]


class PledgeProgramForm(forms.ModelForm):
    date_complete = forms.DateField(
        label=PledgeProgram.verbose_complete,
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    date_initiation = forms.DateField(
        label=PledgeProgram.verbose_initiation,
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )

    class Meta:
        model = PledgeProgram
        fields = [
            "remote",
            "weeks",
            "weeks_left",
            "status",
            "date_complete",
            "date_initiation",
        ]

    def clean_other_manual(self):
        other_manual = self.data.get("other_manual", "")
        other_manual_cleaned = self.cleaned_data.get("other_manual", "")
        if (
            self.cleaned_data.get("manual") == "other"
            and other_manual == ""
            and other_manual_cleaned == ""
        ):
            raise forms.ValidationError(
                "You must submit the other manual your chapter is "
                "following if not one of the approved models."
            )
        if other_manual == "" and other_manual_cleaned != "":
            other_manual = other_manual_cleaned
        return other_manual


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
                Field("user__chapter"),
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
                Field("year"),
                Field("all_complete_status", label="Status All Complete"),
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


class RiskListFilter(forms.Form):
    helper = RiskListFormHelper
    year = forms.ChoiceField(choices=[(2019, "2019"), (2018, "2018")])
    all_complete_status = forms.ChoiceField(
        choices=[(0, "All"), (1, "Complete"), (2, "Incomplete")]
    )
    region = forms.ChoiceField(required=False, choices=Region.region_choices())


class SchoolModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.school}"


class PledgeFormFull(forms.ModelForm):
    school_name = SchoolModelChoiceField(
        queryset=Chapter.objects.all().order_by("school")
    )
    birth_date = forms.DateField(
        label="Birth Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
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

    class Meta:
        model = Pledge
        exclude = ["created", "modified"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["major"].queryset = ChapterCurricula.objects.none()
        if "school_name" in self.data:
            try:
                chapter_id = int(self.data.get("school_name"))
                self.fields["major"].queryset = ChapterCurricula.objects.filter(
                    chapter__pk=chapter_id
                ).order_by("major")
            except (ValueError, TypeError):
                pass  # invalid input from the client; ignore and fallback to empty City queryset
        elif self.instance.pk:
            self.fields[
                "major"
            ].queryset = self.instance.school_name.major_set.order_by("major")
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Accordion(
                AccordionGroup(
                    "Personal Information",
                    Row(
                        Column("title",), Column("first_name",), Column("middle_name",),
                    ),
                    Row(Column("last_name",), Column("suffix",),),
                    "nickname",
                    "parent_name",
                    Row(Column("email_school",), Column("email_personal",),),
                    Row(Column("phone_mobile",), Column("phone_home",),),
                    "address",
                    Row(Column("birth_date",), Column("birth_place",),),
                ),
                AccordionGroup(
                    "College & Degree Information",
                    Row(Column("school_name",), Column("major",),),
                    "grad_date_year",
                    "other_degrees",
                    "relative_members",
                    "other_greeks",
                    "other_tech",
                    "other_frat",
                    InlineRadios("other_college_choice"),
                    "other_college",
                    InlineRadios("explain_expelled_org_choice"),
                    "explain_expelled_org",
                    InlineRadios("explain_expelled_college_choice"),
                    "explain_expelled_college",
                    InlineRadios("explain_crime_choice"),
                    "explain_crime",
                ),
                AccordionGroup(
                    "Pause and Deliberate",
                    HTML(
                        "<h2>Please carefully read and answer each question below honestly</h2>"
                    ),
                    "loyalty",
                    "not_honor",
                    "accountable",
                    "life",
                    "unlawful",
                    "unlawful_org",
                    "brotherhood",
                    "engineering",
                    "engineering_grad",
                    "payment",
                    "attendance",
                    "harmless",
                    "alumni",
                    "honest",
                    "signature",
                ),
                ButtonHolder(Submit("submit", "Submit", css_class="btn-primary")),
            )
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
        queryset=User.objects.all(),
        widget=autocomplete.ModelSelect2(
            url="users:autocomplete",
            forward=(
                forward.Const("true", "chapter"),
                forward.Const("true", "actives"),
            ),
        ),
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
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
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
            url="users:autocomplete", forward=(forward.Const("true", "chapter"),),
        ),
    )
    meeting_date = forms.DateField(
        label="Meeting Date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
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
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    charges_filed = forms.DateField(
        label="Charges filed by majority vote at a chapter meeting on date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    trial_date = forms.DateField(
        label="Trial scheduled for date",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    notify_method = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        choices=[x.value for x in DisciplinaryProcess.METHODS],
    )

    class Meta:
        model = DisciplinaryProcess
        fields = [
            "financial",
            "user",
            "charges",
            "resolve",
            "advisor",
            "faculty",
            "charges_filed",
            "notify_date",
            "notify_method",
            "trial_date",
            "charging_letter",
        ]


class DisciplinaryForm2(forms.ModelForm):
    rescheduled_date = forms.DateField(
        label="When will the new trial be held?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    notify_results_date = forms.DateField(
        label="On what date was the member notified of the results of the trial?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
    )
    suspension_end = forms.DateField(
        label="If suspended, when will this member’s suspension end?",
        widget=DatePicker(
            options={"format": "M/DD/YYYY"}, attrs={"autocomplete": "off"},
        ),
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
