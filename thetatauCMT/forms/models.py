import datetime
import io
import os
import csv
from pathlib import Path
from collections import Counter
import address
from address.models import AddressField
from email.mime.base import MIMEBase
from django.db import models, transaction
from django.db.utils import IntegrityError
from django.contrib.auth.models import Group
from django_userforeignkey.models.fields import UserForeignKey
from django.contrib import messages
from django.core.validators import MaxValueValidator, RegexValidator
from django.conf import settings
from django.utils import timezone
from djmoney.models.fields import MoneyField
from django.utils.translation import gettext_lazy as _
from email_signals.models import EmailSignalMixin
from multiselectfield import MultiSelectField
from viewflow.models import Process
from easy_pdf.rendering import render_to_pdf
from quickbooks.objects.customer import Customer
from quickbooks.objects.attachable import Attachable, AttachableRef
from core.finances import get_quickbooks_client, invoice_search, create_line
from core.models import (
    forever,
    CHAPTER_ROLES_CHOICES,
    CHAPTER_OFFICER_CHOICES,
    academic_encompass_start_end_date,
    semester_encompass_start_end_date,
    EnumClass,
    TimeStampedModel,
    YearTermModel,
    no_future,
    EnumClass,
)
from chapters.models import Chapter
from submissions.models import Submission
from configs.models import Config


class MultiSelectField(MultiSelectField):
    # Not Django 2.0+ ready yet, https://github.com/goinnn/django-multiselectfield/issues/74
    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return self.get_prep_value(value)


class Badge(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=50)
    description = models.CharField(max_length=500)
    cost = models.DecimalField(
        default=0, decimal_places=2, max_digits=7, help_text="Cost of item."
    )

    def __str__(self):
        return f"{self.name}; ${self.cost}"


class Guard(models.Model):
    ONE_LETTER = 1
    TWO_LETTER = 2
    NUM_LETTERS = (
        (ONE_LETTER, "one"),
        (TWO_LETTER, "two"),
    )
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=50)
    letters = models.IntegerField(default=ONE_LETTER, choices=NUM_LETTERS)
    description = models.CharField(max_length=500)
    cost = models.DecimalField(
        default=0, decimal_places=2, max_digits=7, help_text="Cost of item."
    )

    def __str__(self):
        return f"{self.name}; ${self.cost}"


def get_pledge_program_upload_path(instance, filename):
    return os.path.join(
        "submissions",
        "pledge_programs",
        f"{instance.chapter.slug}_{instance.year}_{instance.term}_{filename}",
    )


class PledgeProgram(YearTermModel, TimeStampedModel, EmailSignalMixin):
    BOOL_CHOICES = ((True, "Yes"), (False, "No"))

    class Meta:
        unique_together = (
            "chapter",
            "year",
            "term",
        )

    class MANUALS(EnumClass):
        basic = ("basic", "Basic")
        nontrad = ("nontrad", "Non-traditional")
        standard = ("standard", "Standard")
        other = ("other", "Other")

    class STATUS(EnumClass):
        none = ("none", "")
        initiated = (
            "initiated",
            "We completed new member education and initiated our pledges.",
        )
        still_initiate = (
            "still_initiate",
            "We completed new member education and voted, we just have to initiate our pledges.",
        )
        still_vote = (
            "still_vote",
            "We completed new member education but we still need to vote and initiate our pledges.",
        )
        not_complete = ("not_complete", "We did not complete new member education.")

    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="pledge_programs"
    )
    verbose_remote = "Have you or will you conduct your new member education remotely?"
    remote = models.BooleanField(verbose_remote, choices=BOOL_CHOICES, default=False)
    verbose_dues = "How much are your chapter's PNM dues, including the pledge fee but NOT including the initiation fee or badge cost?"
    dues = models.PositiveIntegerField(verbose_dues, default=0)
    verbose_start = "When did you/do you anticipate starting new member education?"
    date_start = models.DateField(verbose_start, default=timezone.now)
    verbose_complete = "When did you/do you anticipate completing new member education?"
    date_complete = models.DateField(verbose_complete, default=timezone.now)
    verbose_initiation = "When did you/do you plan to initiate your pledges?"
    date_initiation = models.DateField(verbose_initiation, default=timezone.now)
    verbose_weeks = "How many weeks is your typical new member education program?"
    weeks = models.PositiveIntegerField(verbose_weeks, default=0)
    verbose_weeks_left = (
        "How many weeks of new member education do you have yet to complete?"
    )
    weeks_left = models.PositiveIntegerField(verbose_weeks_left, default=0)
    status = models.CharField(
        verbose_name="What is the current status of your new member education?",
        max_length=20,
        choices=[x.value for x in STATUS],
        default="none",
    )
    manual = models.CharField(max_length=10, choices=[x.value for x in MANUALS])
    other_manual = models.FileField(
        upload_to=get_pledge_program_upload_path, null=True, blank=True
    )
    schedule = models.FileField(
        upload_to=get_pledge_program_upload_path, null=True, blank=True
    )
    test = models.FileField(
        upload_to=get_pledge_program_upload_path, null=True, blank=True
    )

    def __str__(self):
        return f"Pledge Program for {self.chapter}"

    @classmethod
    def signed_this_year(cls, chapter):
        """
        If the current term is the spring, the form could have been submitted
        in the fall of last year.
        :param chapter:
        :return: form for current year, semester for chapter
        """
        program_fa = None
        if YearTermModel.current_term() == "sp":
            program_fa = cls.objects.filter(
                chapter=chapter,
                year=YearTermModel.current_year() - 1,
                term="fa",
            ).first()
        program = cls.signed_this_semester(chapter)
        return program or program_fa

    @classmethod
    def signed_this_semester(cls, chapter):
        program = cls.objects.filter(
            chapter=chapter,
            year=YearTermModel.current_year(),
            term=YearTermModel.current_term(),
        ).first()
        return program


class PledgeProgramProcess(Process, EmailSignalMixin):
    class APPROVAL(EnumClass):
        approved = ("approved", "Approved")
        revisions = ("revisions", "Revisions needed")
        denied = ("denied", "Denied")
        not_reviewed = ("not_reviewed", "Not Reviewed")

    approval = models.CharField(
        verbose_name="Pledge program approval status",
        max_length=20,
        choices=[x.value for x in APPROVAL],
        default="not_reviewed",
    )
    approval_comments = models.TextField(
        _("If rejecting, please explain why."), blank=True
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="pledge_program_process"
    )
    program = models.ForeignKey(
        PledgeProgram,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="process",
    )

    def __str__(self):
        return f"Pledge Program Process for {self.chapter}"


class Initiation(TimeStampedModel, EmailSignalMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="initiation"
    )
    # The user chapter could change, so we record the initiation chapter
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        related_name="initiations",
        blank=True,
        null=True,
    )
    date_graduation = models.DateField(default=timezone.now)
    date = models.DateField(
        "Initiation Date", default=timezone.now, validators=[no_future]
    )
    roll = models.PositiveIntegerField(default=999999999)
    gpa = models.FloatField()
    test_a = models.IntegerField(validators=[MaxValueValidator(100)])
    test_b = models.IntegerField(validators=[MaxValueValidator(100)])
    badge = models.ForeignKey(
        Badge, on_delete=models.SET_NULL, related_name="initiation", null=True
    )
    guard = models.ForeignKey(
        Guard, on_delete=models.SET_NULL, related_name="initiation", null=True
    )

    # task = GenericRelation(TaskChapter)  We are currently not using this

    # def __str__(self):
    #     return f"{self.user} initiated on {self.date}"

    def save(self, *args, **kwargs):
        status_update = True
        if "status_update" in kwargs:
            status_update = kwargs.pop("status_update")
        super().save(*args, **kwargs)
        # Need to adjust old status pnm, save new status active
        self.user.badge_number = self.roll
        try:
            with transaction.atomic():
                self.user.save()
        except IntegrityError as e:
            print("User ALREADY EXISTS", str(e))
        if status_update:
            self.user.set_current_status(
                status="activepend", start=self.date, created=self.created
            )

    def chapter_initiations(self, chapter):
        result = self.objects.filter(user__chapter=chapter)
        return result


class Depledge(TimeStampedModel, EmailSignalMixin):
    class REASONS(EnumClass):
        volunteer = ("volunteer", "Voluntarily decided not to continue")
        time = ("time", "Unable/unwilling to meet time commitment")
        grades = ("grades", "Unable/unwilling to meet academic requirement")
        financial = ("financial", "Unable/unwilling to meet financial commitment")
        violation = ("violation", "Policy/Procedure Violation")
        vote = ("vote", "Poor fit with the chapter/candidate chapter")
        withdrew = ("withdrew", "Withdrew from Engineering/University")
        transfer = ("transfer", "Transferring to another school")
        other = ("other", "Other")

    class MEETING(EnumClass):
        virtual = ("virtual", "Virtual")
        in_person = ("in_person", "In Person")
        no = ("no", "No")
        na = ("na", "Not Applicable")

    class ITEMS(EnumClass):
        pin = ("pin", "Pledge Pin")
        manual = ("manual", "Membership Manual")
        other = ("other", "Other")
        na = ("na", "No Items Given")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="depledge"
    )
    reason = models.CharField(max_length=10, choices=[x.value for x in REASONS])
    reason_other = models.CharField(
        "Other reason for depledging",
        max_length=100,
        null=True,
        blank=True,
    )
    date = models.DateField(
        "Depledge Date", default=timezone.now, validators=[no_future]
    )
    meeting_held = models.CharField(
        "Was a meeting held with the depledged PNM?",
        max_length=10,
        choices=[x.value for x in MEETING],
        default="na",
    )
    meeting_date = models.DateField(
        "When was the meeting with the depledged PNM?",
        default=timezone.now,
        validators=[no_future],
        null=True,
        blank=True,
    )
    meeting_attend = MultiSelectField(
        "Who attended the meeting with the depledged PNM?",
        choices=[
            ("None", "None"),
            ("pledge/new member educator", "Pledge/New Member Educator"),
            ("recruitment chair", "Recruitment Chair"),
            ("risk management chair", "Risk Management Chair"),
            ("marshal", "Marshal"),
            ("other appointee", "Other Appointee"),
        ]
        + CHAPTER_OFFICER_CHOICES,
        null=True,
        blank=True,
        max_length=500,
    )
    meeting_not = models.CharField(
        "Why was there no meeting with the depledged PNM?",
        max_length=100,
        null=True,
        blank=True,
    )
    informed = models.CharField(
        "By whom and how was the depledged PNM informed?",
        max_length=100,
        null=True,
        blank=True,
    )
    concerns = models.CharField(
        "Did the depledged PNM express any concerns?",
        max_length=200,
        null=True,
        blank=True,
    )
    returned_items = MultiSelectField(
        "Have the following items been returned?",
        max_length=100,
        choices=[x.value for x in ITEMS],
        null=True,
        blank=True,
    )
    returned_other = models.CharField(
        "Other returned items",
        max_length=100,
        null=True,
        blank=True,
    )
    extra_notes = models.TextField(
        "Is there anything else national Theta Tau should know?",
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.user} depledged on {self.date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.user.set_current_status(
            status="depledge",
            created=self.created,
            start=self.date,
        )


class StatusChange(TimeStampedModel):
    class REASONS(EnumClass):
        graduate = ("graduate", "Member is graduating")  # Graduated from school
        coop = ("coop", "Member is going on CoOp or Study abroad")  # Co-Op/Internship
        covid = (
            "covid",
            "Member is leaving for the semester due to COVID-19",
        )
        military = (
            "military",
            "Member is being deployed",
        )  # Called to Active/Reserve Military Duty
        withdraw = (
            "withdraw",
            "Member is withdrawing from school",
        )  # Withdrawing from school
        transfer = (
            "transfer",
            "Member is transferring to another school",
        )  # Transferring to another school
        resignedCC = ("resignedCC", "Member is resigning from candidate chapter")

    class DEGREES(EnumClass):
        BS = ("bs", "Bachelor of Science")
        MS = ("ms", "Master of Science")
        MBA = ("mba", "Master of Business Administration")
        PhD = ("phd", "Doctor of Philosophy")
        BA = ("ba", "Bachelor of Arts")
        MA = ("ma", "Master of Arts")
        ME = ("me", "Master of Engineering")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="status_changes",
    )
    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="statuschange_created",
    )
    reason = models.CharField(max_length=10, choices=[x.value for x in REASONS])

    degree = models.CharField(max_length=4, choices=[x.value for x in DEGREES])
    date_start = models.DateField("Start Date", default=timezone.now)
    date_end = models.DateField("End Date", default=forever, blank=True)
    employer = models.CharField(max_length=200)
    miles = models.PositiveIntegerField(default=0, help_text="Miles from campus.")
    email_work = models.EmailField(_("email address"), blank=True)
    new_school = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        default=None,
        related_name="transfers",
        null=True,
        blank=True,
    )

    # task = GenericRelation(TaskChapter)

    def __str__(self):
        return f"{self.user} {self.reason} on {self.date_start}"

    def save_only(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # if graduate, withdraw, transfer
        #   save new status alumni
        # if coop, military
        #   save new status away
        if self.reason in ["graduate", "withdraw", "transfer", "resignedCC"]:
            self.user.set_current_status(
                created=self.created,
                status="alumni",
                start=self.date_start,
            )
        else:
            # military, coop, covid
            self.user.set_current_status(
                created=self.created,
                status="away",
                start=self.date_start,
                end=self.date_end,
            )
            # User will return active as soon as away ends
            self.user.set_current_status(
                created=self.created,
                status="active",
                start=self.date_end + datetime.timedelta(days=1),
                current=False,
            )


def get_chapter_report_upload_path(instance, filename):
    return os.path.join(
        "submissions",
        "chapter_report",
        f"{instance.chapter.slug}_{instance.year}_{instance.term}_{filename}",
    )


class ChapterReport(YearTermModel, TimeStampedModel, EmailSignalMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chapter_form"
    )
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="info")
    report = models.FileField(upload_to=get_chapter_report_upload_path)

    def __str__(self):
        return f"Chapter Report for {self.chapter}"

    @classmethod
    def signed_this_semester(cls, chapter, report=True):
        program = cls.objects.filter(
            chapter=chapter,
            year=YearTermModel.current_year(),
            term=YearTermModel.current_term(),
        )

        if report:
            program = program.exclude(report__in=[""])
        program = program.last()
        return program


def get_chapter_education_upload_path(instance, filename):
    return os.path.join(
        "submissions",
        "chapter_education",
        f"{instance.chapter.slug}_{instance.program_date}_{instance.category}_{filename}",
    )


class HSEducation(Process, TimeStampedModel, EmailSignalMixin):
    class CATEGORIES(EnumClass):
        alcohol_drugs = ("alcohol_drugs", "Alcohol and Drug Awareness")
        harassment = ("harassment", "Anti-Harassment")
        mental = ("mental", "Mental Health Recognition")

    class APPROVAL(EnumClass):
        approved = ("approved", "Approved")
        revisions = ("revisions", "Revisions needed")
        denied = ("denied", "Denied")
        not_reviewed = ("not_reviewed", "Not Reviewed")

    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="hseducation_created",
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="education"
    )
    report = models.FileField(upload_to=get_chapter_education_upload_path)
    program_date = models.DateField(default=timezone.now)
    category = models.CharField(
        "Program category",
        max_length=20,
        choices=[x.value for x in CATEGORIES],
    )
    first_name = models.CharField(
        _("facilitator first name"), max_length=30, blank=True
    )
    last_name = models.CharField(_("facilitator last name"), max_length=150, blank=True)
    email = models.EmailField(_("facilitator email address"), blank=True)
    title = models.CharField(
        _("facilitator title"),
        blank=True,
        max_length=5,
        choices=[
            ("mr", "Mr."),
            ("miss", "Miss"),
            ("ms", "Ms"),
            ("mrs", "Mrs"),
            ("mx", "Mx"),
            ("none", ""),
        ],
    )
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
    )
    phone_number = models.CharField(
        _("facilitator phone number"),
        validators=[phone_regex],
        max_length=17,
        blank=True,
        help_text="Format: 9999999999 no spaces, dashes, etc.",
    )
    approval = models.CharField(
        verbose_name="Program approval status",
        max_length=20,
        choices=[x.value for x in APPROVAL],
        default="not_reviewed",
    )
    approval_comments = models.TextField(
        _("If rejecting, please explain why."), blank=True
    )

    def __str__(self):
        return f"H&S Education {self.category} for {self.chapter}"

    @classmethod
    def submitted_this_year(cls, chapter):
        start, end = academic_encompass_start_end_date()
        programs = cls.objects.filter(
            chapter=chapter,
            created__gt=start,
            created__lt=end,
        )
        return programs


class RiskManagement(YearTermModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="risk_form"
    )
    role = models.CharField(max_length=254)
    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="risk_management_forms",
        null=True,
    )
    date = models.DateField("Submit Date", default=timezone.now)
    alcohol = models.BooleanField()
    hosting = models.BooleanField()
    monitoring = models.BooleanField()
    member = models.BooleanField()
    officer = models.BooleanField()
    abusive = models.BooleanField()
    hazing = models.BooleanField()
    substances = models.BooleanField()
    high_risk = models.BooleanField()
    transportation = models.BooleanField()
    property_management = models.BooleanField()
    guns = models.BooleanField()
    trademark = models.BooleanField()
    social = models.BooleanField()
    indemnification = models.BooleanField()
    agreement = models.BooleanField()
    electronic_agreement = models.BooleanField()
    photo_release = models.BooleanField(default=False)
    arbitration = models.BooleanField(default=False)
    dues = models.BooleanField(default=False)
    fines = models.BooleanField(default=False)
    terms_agreement = models.BooleanField()
    typed_name = models.CharField(max_length=255)

    @staticmethod
    def risk_forms_chapter_semester(chapter, date):
        actives = chapter.active_actives()
        start, end = semester_encompass_start_end_date(date)
        return RiskManagement.objects.filter(
            user__in=actives, date__gte=start, date__lte=end
        )

    @staticmethod
    def risk_forms_semester(date):
        """
        given a date determine RMP submissions in that time
        """
        start, end = semester_encompass_start_end_date(date)
        return RiskManagement.objects.filter(date__gte=start, date__lte=end)

    @staticmethod
    def user_signed_this_semester(user):
        start, end = semester_encompass_start_end_date()
        signed_before = user.risk_form.filter(date__gte=start, date__lte=end)
        return signed_before


class Audit(YearTermModel, TimeStampedModel, EmailSignalMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="audit_form"
    )
    dues_member = models.FloatField("Member Dues")
    dues_pledge = models.FloatField("Potential New Member Pledging Fees/Dues")
    frequency = models.CharField(
        "What is the frequency of member dues",
        max_length=10,
        choices=[
            ("month", "month"),
            ("semester", "semester"),
            ("quarter", "quarter"),
            ("year", "year"),
        ],
    )
    payment_plan = models.BooleanField()
    cash_book = models.BooleanField()
    cash_register = models.BooleanField()
    member_account = models.BooleanField()
    cash_book_reviewed = models.BooleanField()
    cash_register_reviewed = models.BooleanField()
    member_account_reviewed = models.BooleanField()
    balance_checking = models.FloatField("Balance of chapter checking account")
    balance_savings = models.FloatField("Balance of chapter savings account")
    debit_card = models.BooleanField()
    debit_card_access = MultiSelectField(
        "Which members have access to the chapter debit card? Select all that apply.",
        choices=[("None", "None")] + CHAPTER_ROLES_CHOICES,
        max_length=5000,
    )
    agreement = models.BooleanField()

    def __str__(self):
        return f"Audit for {self.user.chapter} by {self.user}"


class Pledge(TimeStampedModel, EmailSignalMixin):
    BOOL_CHOICES = ((True, "Yes"), (False, "No"))
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pledge_form",
        default=1,
    )
    signature = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name"
    )
    parent_name = models.CharField(
        _("Parent / Guardian Name"), blank=True, null=True, max_length=60
    )
    parent_email = models.EmailField(
        _("Parent / Guardian Email"), blank=True, null=True
    )
    birth_place = models.CharField(
        _("Place of Birth"),
        max_length=50,
        help_text=_("City and state or province is sufficient"),
    )
    other_degrees = models.CharField(
        _("College degrees already received"),
        max_length=60,
        blank=True,
        help_text="Name of Major/Field of that Degree. If none, leave blank",
    )
    relative_members = models.CharField(
        _(
            "Indicate the names of any relatives you have who are members of Theta Tau below"
        ),
        max_length=60,
        blank=True,
        help_text="Include relationship, chapter, and graduation year, if known. If none, leave blank",
    )
    other_greeks = models.CharField(
        _("Of which Greek Letter Honor Societies are you a member?"),
        max_length=60,
        blank=True,
        help_text="If none, leave blank",
    )
    other_tech = models.CharField(
        _("Of which technical societies are you a member?"),
        max_length=60,
        blank=True,
        help_text="If none, leave blank",
    )
    other_frat = models.CharField(
        _("Of which fraternities are you a member?"),
        max_length=60,
        blank=True,
        help_text="Other than Theta Tau -- If no other, leave blank",
    )
    other_college = models.CharField(
        _("Which? (Other college(s))"), max_length=60, blank=True
    )
    explain_expelled_org = models.TextField(_("If yes, please explain."), blank=True)
    explain_expelled_college = models.TextField(
        _("If yes, please explain."), blank=True
    )
    explain_crime = models.TextField(_("If yes, please explain."), blank=True)
    verbose_loyalty = _(
        "The purpose of Theta Tau shall be to develop and maintain a high standard of professional interest among "
        "its members and to unite them in a strong bond of fraternal fellowship. The members are pledged to help one "
        "another professionally and personally in a practical way, as students and as alumni, advising as to "
        "opportunities for service and advancement, warning against unethical practices and persons. Do you believe "
        "that such a fraternity is entitled to your continued support and loyalty?"
    )
    loyalty = models.BooleanField(verbose_loyalty, choices=BOOL_CHOICES, default=False)
    verbose_not_honor = _(
        "Theta Tau is a fraternity, not an honor society. It aims to elect no one to any class of membership solely "
        "in recognition of his scholastic or professional achievements. Do you subscribe to this doctrine?"
    )
    not_honor = models.BooleanField(
        verbose_not_honor, choices=BOOL_CHOICES, default=False
    )
    verbose_accountable = _(
        "Do you understand, if you become a member of Theta Tau, that the other members will have the right to hold "
        "you accountable for your conduct? Do you further understand that the Fraternity has Risk Management policies "
        "(hazing, alcohol, etc) with which you are expected to comply and to which you should expect others to comply?"
    )
    accountable = models.BooleanField(
        verbose_accountable, choices=BOOL_CHOICES, default=False
    )
    verbose_life = _(
        "When you assume the oaths or obligations required during initiation, will you agree that they are binding "
        "on the member for life?"
    )
    life = models.BooleanField(verbose_life, choices=BOOL_CHOICES, default=False)
    verbose_unlawful = _(
        "Do you promise that you will not permit the use of a Theta Tau headquarters or meeting place for unlawful "
        "purposes?"
    )
    unlawful = models.BooleanField(
        verbose_unlawful, choices=BOOL_CHOICES, default=False
    )
    verbose_unlawful_org = _(
        "This Fraternity requires of its initiates that they shall not be members of any sect or organization which "
        "teaches or practices activities in violation of the laws of the state or the nation. Do you subscribe to this "
        "requirement?"
    )
    unlawful_org = models.BooleanField(
        verbose_unlawful_org, choices=BOOL_CHOICES, default=False
    )
    verbose_brotherhood = _(
        "The strength of the Fraternity depends largely on the character of its members and the close and loyal "
        "friendship uniting them. Do you realize you have no right to join if you do not act on this belief?"
    )
    brotherhood = models.BooleanField(
        verbose_brotherhood, choices=BOOL_CHOICES, default=False
    )
    verbose_engineering = _(
        "Theta Tau is an engineering fraternity whose student membership is limited to those regularly enrolled in "
        "a course leading to a degree in an approved engineering curriculum. Members of other fraternities that "
        "restrict their membership to any, or several engineering curricula are generally not eligible to Theta Tau, "
        "nor may our members join such fraternities. Engineering honor societies such as Tau Beta Pi, Eta Kappa Nu, "
        "etc., are not included in this classification. Do you fully understand and subscribe to that policy?"
    )
    engineering = models.BooleanField(
        verbose_engineering, choices=BOOL_CHOICES, default=False
    )
    verbose_engineering_grad = _(
        """Is it your intention to practice engineering after graduation?"""
    )
    engineering_grad = models.BooleanField(
        verbose_engineering_grad, choices=BOOL_CHOICES, default=False
    )
    verbose_payment = _(
        "The Fraternity has a right to demand from you prompt payment of bills. Do you understand, and are you "
        "ready to accept, the financial obligations of becoming a member?"
    )
    payment = models.BooleanField(verbose_payment, choices=BOOL_CHOICES, default=False)
    verbose_attendance = _(
        "The Fraternity has a right to demand from you regular attendance at meetings and faithful performance of "
        "duties entrusted to you. Are you ready to accept such obligations?"
    )
    attendance = models.BooleanField(
        verbose_attendance, choices=BOOL_CHOICES, default=False
    )
    verbose_harmless = _(
        "Do you agree hereby to fully and completely release, discharge, and hold harmless the Chapter, "
        "House Corporation, Theta Tau (the national Fraternity), and their respective members, officers, agents, "
        "and any other entity whose liability is derivative by or through said released parties from all past, "
        "present and future claims, causes of action and liabilities of any nature whatsoever, regardless of the cause "
        "of the damage or loss, and including, but not limited to, claims and losses covered by insurance, claims and "
        "damages for property, for personal injury, for premises liability, for torts of any nature, and claims for "
        "compensatory damages, consequential damages or punitive/exemplary damages? Your affirmative answer binds you, "
        "under covenant, not to sue any of the previously named entities."
    )
    harmless = models.BooleanField(
        verbose_harmless, choices=BOOL_CHOICES, default=False
    )
    verbose_alumni = _(
        "As an alumnus, you should join with other alumni in the formation and support of alumni clubs or "
        "associations. Furthermore, on October 15th of each year, celebrations are held throughout the country to "
        "recall the founding of our Fraternity and to honor the Founders. Members of Theta Tau are encouraged to send "
        "some form of greeting to their chapters on or about October 15th. If several members are located in the same "
        "vicinity they could gather for an informal meeting. Will you endeavor to do these things, as circumstances "
        "permit, after you are initiated into Theta Tau?"
    )
    alumni = models.BooleanField(verbose_alumni, choices=BOOL_CHOICES, default=False)
    verbose_honest = _(
        """My answers to these questions are my honest and sincere convictions."""
    )
    honest = models.BooleanField(verbose_honest, choices=BOOL_CHOICES, default=False)
    verbose_bill = _(
        "I understand and have read the potential new member bill of rights."
    )
    bill = models.BooleanField(verbose_bill, choices=BOOL_CHOICES, default=False)

    def __str__(self):
        return f"Pledge Form {self.user}"


def get_premature_alumn_upload_path(instance, filename):
    return os.path.join(
        "submissions",
        "prealumn",
        f"{instance.user.chapter.slug}_{instance.user.id}_{filename}",
    )


class PrematureAlumnus(Process, EmailSignalMixin):
    class TYPES(EnumClass):
        less4 = (
            "less4",
            "Undergraduate Student (initiated into Theta Tau less than four years ago.)",
        )
        more4 = (
            "more4",
            "Undergraduate Student initiated into Theta Tau 4 or more years ago.",
        )
        grad = (
            "grad",
            "Student in Graduate school at the school where initiated as an undergraduate.",
        )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="prealumn_form",
        null=True,
        blank=True,
    )
    form = models.FileField(upload_to=get_premature_alumn_upload_path)
    verbose_good_standing = _("""Member is in good standing of Theta Tau.""")
    good_standing = models.BooleanField(verbose_good_standing, default=False)
    verbose_financial = _(
        """Member has no current financial obligation to the chapter."""
    )
    financial = models.BooleanField(verbose_financial, default=False)
    verbose_semesters = _(
        """Member has completed at least six months of active membership."""
    )
    semesters = models.BooleanField(verbose_semesters, default=False)
    verbose_lifestyle = _(
        "Member has had a significant lifestyle change preventing adequately "
        "& responsibly fulfilling duties & obligations."
    )
    lifestyle = models.BooleanField(verbose_lifestyle, default=False)
    verbose_consideration = _(
        "I understand that this status change request is submitted "
        "to the Executive Director for consideration."
    )
    consideration = models.BooleanField(verbose_consideration, default=False)
    verbose_prealumn_type = _("""Type of Premature (“Early”) Alumnus Status""")
    prealumn_type = models.CharField(
        verbose_prealumn_type,
        default="less4",
        max_length=10,
        choices=[x.value for x in TYPES],
    )
    approved_exec = models.BooleanField("Executive Director Approved", default=False)
    exec_comments = models.TextField(_("If rejecting, please explain why."), blank=True)
    verbose_vote = _(
        """The status change for the member was approved by a four-fifths favorable vote of the chapter."""
    )
    vote = models.BooleanField(verbose_vote, default=False)

    def __str__(self):
        return f"Premature Alumnus for {self.user}"


def get_badge_order_upload_path(instance, filename):
    return os.path.join(
        "submissions",
        "initiation",
        f"{instance.chapter.slug}_{instance.invoice}_{filename}",
    )


class InitiationProcess(Process, EmailSignalMixin):
    class CEREMONIES(EnumClass):
        normal = (
            "normal",
            "Normal in-person ceremony",
        )
        extra = (
            "extra",
            "In-person extraordinary initiation ceremony",
        )
        remote = (
            "remote",
            "Remote extraordinary initiation ceremony",
        )

    initiations = models.ManyToManyField(Initiation, related_name="process", blank=True)
    invoice = models.PositiveIntegerField("Invoice Number", default=999999999)
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="initiation_process"
    )
    verbose_ceremony = "What ceremony did you use to initiate these members?"
    scheduled_date = models.DateField(
        "Date order scheduled to be shipped on", default=timezone.now
    )
    ceremony = models.CharField(
        verbose_ceremony,
        default="normal",
        max_length=10,
        choices=[x.value for x in CEREMONIES],
    )
    badge_order = models.FileField(
        blank=True, null=True, upload_to=get_badge_order_upload_path
    )

    def __str__(self):
        return f"Initiation Process for {self.chapter}"

    def get_fees(self, chapter, initiation):
        init_fee = Config.get_value("init_fee_chapter")
        if chapter.candidate_chapter:
            init_fee = Config.get_value("init_fee_candidate_chapter")
        late_fee = 0
        init_date = initiation.date
        init_submit = initiation.created.date()
        delta = init_submit - init_date
        if delta.days > 28:
            if not chapter.candidate_chapter:
                late_fee = Config.get_value("init_late_fee")
        return float(init_fee), float(late_fee)

    def generate_blackbaud_update(self, invoice=False, response=None, file_obj=False):
        """
        invoice is when the file is for an invoice, otherwise used for badge orders
        response is to send a file to the user in the browser
            if no response assume want to email the file add to
        file_obj is when we want file to send to quickbooks not email and not response
        """
        INIT = [
            "Date Submitted",
            "Chapter Name",
            "Initiation Date",
            "Graduation Year",
            "Roll Number",
            "First Name",
            "Middle Name",
            "Last Name",
            "Overall GPA",
            "A Pledge Test Scores",
            "B Pledge Test Scores",
            "Initiation Fee",
            "Late Fee",
            "Badge Style",
            "Badge Cost",
            "Sum for member",
        ]
        update_remove = ["Date Submitted", "Sum for member"]
        if not invoice:
            for column in update_remove:
                INIT.remove(column)
        chapter = self.chapter.name
        # chapter_abr = self.chapter.greek
        init_date = self.initiations.first().date.strftime("%Y%m%d")
        filename = f"{chapter}_{init_date}_initiation.csv"
        if response is not None:
            init_file = response
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            out = None
        else:
            init_file = io.StringIO()
            init_mail = MIMEBase("application", "csv")
            init_mail.add_header("Content-Disposition", "attachment", filename=filename)
        writer = csv.DictWriter(init_file, fieldnames=INIT)
        writer.writeheader()
        for initiation in self.initiations.all():
            badge = initiation.badge
            badge_code = ""
            badge_cost = 0
            if badge:
                badge_code = badge.code
                badge_cost = float(badge.cost)
            chapter = initiation.user.chapter
            init_fee, late_fee = self.get_fees(chapter, initiation)
            init_submit = initiation.created.date()
            total = badge_cost + init_fee + late_fee
            row = {
                "Date Submitted": init_submit,
                "Initiation Date": init_date,
                "Chapter Name": chapter.name,
                "Graduation Year": initiation.user.graduation_year,
                "Roll Number": initiation.roll,
                "First Name": initiation.user.first_name,
                "Middle Name": "",
                "Last Name": initiation.user.last_name,
                "Overall GPA": initiation.gpa,
                "A Pledge Test Scores": initiation.test_a,
                "B Pledge Test Scores": initiation.test_b,
                "Initiation Fee": init_fee,
                "Late Fee": late_fee,
                "Badge Style": badge_code,
                "Badge Cost": badge_cost,
                "Sum for member": total,
            }
            if not invoice:
                for column in update_remove:
                    row.pop(column, None)
            writer.writerow(row)
        if response is None and not file_obj:
            init_mail.set_payload(init_file.getvalue())
            out = init_mail
        elif file_obj:
            filepath = Path(r"exports/" + filename)
            with open(filepath, mode="w", newline="") as f:
                print(init_file.getvalue(), file=f)
            out = filepath
        return out

    def sync_badge_shingle_invoice(self, request, invoice_number):
        """
        This will sync with quickbooks
        """
        client = get_quickbooks_client()
        chapter = self.chapter
        if chapter.candidate_chapter:
            messages.add_message(
                request, messages.ERROR, "Candidate chapters do not pay initiation fees"
            )
            return
        chapter_name = chapter.name
        customer = Customer.query(
            select=f"SELECT * FROM Customer WHERE CompanyName LIKE '{chapter_name} chapter%'",
            qb=client,
        )
        if customer:
            customer = customer[0]
        else:
            messages.add_message(
                request,
                messages.ERROR,
                f"Quickbooks Customer matching name: '{chapter_name} Chapter...' not found",
            )
            return
        invoice, linenumber_count = invoice_search(invoice_number, customer, client)
        late_fee_count = 0
        fee_count = 0
        for initiation in self.initiations.all():
            _, late_fee = self.get_fees(self.chapter, initiation)
            if not late_fee:
                fee_count += 1
            else:
                late_fee_count += 1
        if fee_count:
            line = create_line(fee_count, linenumber_count, name="I1A", client=client)
            invoice.Line.append(line)
            linenumber_count += 1
        if late_fee_count:
            line = create_line(
                late_fee_count, linenumber_count, name="I1B", client=client
            )
            invoice.Line.append(line)
        badge_count = Counter(self.initiations.values_list("badge__code", flat=True))
        for badge_guard_code, count in badge_count.items():
            if badge_guard_code == "None":
                continue
            line = create_line(
                count, linenumber_count, name=badge_guard_code, client=client
            )
            invoice.Line.append(line)
            linenumber_count += 1
        memo = "Initiated: " + ", ".join(
            self.initiations.values_list("user__name", flat=True)
        )
        old_memo = invoice.CustomerMemo.value
        memo = old_memo + "\n" + memo if old_memo else memo
        # Maximum 1000 chars
        memo = memo[0:999]
        invoice.CustomerMemo.value = memo
        invoice.DeliveryInfo = None
        invoice_obj = invoice.save(qb=client)
        attachment_path = self.generate_blackbaud_update(invoice=True, file_obj=True)
        attachment = Attachable()
        attachable_ref = AttachableRef()
        attachable_ref.EntityRef = invoice.to_ref()
        attachable_ref.IncludeOnSend = True
        attachment.AttachableRef.append(attachable_ref)
        attachment.FileName = attachment_path.name
        attachment._FilePath = str(attachment_path.absolute())
        attachment.ContentType = "text/csv"
        attachment.save(qb=client)
        if attachment_path.exists():
            attachment_path.unlink()  # Delete the file when we are done
        return invoice_obj.DocNumber

    def generate_badge_shingle_order(
        self, response=None, csv_type=None, get_file=False
    ):
        """
        badge example:
        Omega Delta, OmgD, 111, 2022, Doe, 107

        shingle example:
        John, , Doe, Omega Delta, 2022, January 18, 2020

        Send Shipments to:
            NAME
            ADDRESS 1
            ADDRESS 2
        """
        badge_header = [
            "Chapter Name",
            "Chapter Address",
            "Chapter Contact",
            "Chapter Phone",
            "Chapter Description",
            "Roll Number",
            "Education Class of",
            "Last Name",
            "Badge Style",
        ]
        shingle_header = [
            "First Name",
            "Middle Name",
            "Last Name",
            "Chapter Name",
            "Chapter Address",
            "Chapter Contact",
            "Chapter Phone",
            "Education Class of",
            "Initiation Date",
            "Email",
            "School Email",
            "Badge Number",
            "Chapter Abbreviation",
            "Badge Style",
        ]
        chapter = self.chapter.name
        chapter_abr = self.chapter.greek
        init_date = self.initiations.first().date.strftime("%Y%m%d")
        badge_file = io.StringIO()
        shingle_file = io.StringIO()
        badge_mail = MIMEBase("application", "csv")
        badge_filename = f"{chapter}_{init_date}_badge.csv"
        # Intuit Invoice # - ChapterID_other stuff.csv
        shingle_filename = (
            f"{self.invoice}-{self.chapter.id:03d}_{chapter}_{init_date}_shingle.csv"
        )
        badge_mail.add_header(
            "Content-Disposition", "attachment", filename=badge_filename
        )
        shingle_mail = MIMEBase("application", "csv")
        shingle_mail.add_header(
            "Content-Disposition", "attachment", filename=shingle_filename
        )
        if response is not None:
            if csv_type == "badge":
                badge_file = response
                filename = badge_filename
            else:
                shingle_file = response
                filename = shingle_filename
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            out = None
        badge_writer = csv.DictWriter(badge_file, fieldnames=badge_header)
        shingle_writer = csv.DictWriter(shingle_file, fieldnames=shingle_header)
        badge_writer.writeheader()
        shingle_writer.writeheader()
        for initiation in self.initiations.all():
            badge = ""
            if initiation.badge:
                badge = initiation.badge.code
            try:
                chapter_address = self.chapter.address
            except address.models.Address.DoesNotExist:
                chapter_address = "NOT SET, UPDATE ASAP"
            row_badge = {
                "Chapter Name": chapter,
                "Chapter Address": chapter_address,
                "Chapter Contact": self.chapter.address_contact,
                "Chapter Phone": self.chapter.address_phone_number,
                "Chapter Description": chapter_abr,
                "Roll Number": initiation.roll,
                "Education Class of": initiation.date_graduation.year,
                "Last Name": initiation.user.last_name,
                "Badge Style": badge,
            }
            badge_writer.writerow(row_badge)
            row_shingle = {
                "First Name": initiation.user.first_name,
                "Middle Name": "",
                "Last Name": initiation.user.last_name,
                "Chapter Name": chapter,
                "Chapter Address": self.chapter.address,
                "Chapter Contact": self.chapter.address_contact,
                "Chapter Phone": self.chapter.address_phone_number,
                "Education Class of": initiation.date_graduation.year,
                "Initiation Date": initiation.date.strftime("%B %d, %Y"),
                "Email": initiation.user.email,
                "School Email": initiation.user.email_school,
                "Badge Number": initiation.roll,
                "Chapter Abbreviation": chapter_abr,
                "Badge Style": badge,
            }
            shingle_writer.writerow(row_shingle)
        if response is None and not get_file:
            badge_mail.set_payload(badge_file.getvalue())
            shingle_mail.set_payload(shingle_file.getvalue())
            out = badge_mail, shingle_mail
        elif get_file:
            if csv_type == "badge":
                file_name = badge_filename
                file_obj = badge_file
            else:
                file_name = shingle_filename
                file_obj = shingle_file
            out = file_name, file_obj
        return out


class Convention(Process, YearTermModel):
    BOOL_CHOICES = ((True, "Approve"), (False, "Deny"))
    BOOL_CHOICES_UNDERSTAND = ((True, "Yes"), (False, "No"))
    meeting_date = models.DateField(default=timezone.now, validators=[no_future])
    delegate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="delegate",
        verbose_name="Delegate Signature",
    )
    alternate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="alternate",
        verbose_name="Alternate Signature",
    )
    verbose_understand = _(
        """I have read and understand the "Convention Expenses" and the "Alcohol Policy
        for National Meetings" policies in the Theta Tau Policies and Procedures Manual."""
    )
    understand_del = models.BooleanField(
        verbose_understand, choices=BOOL_CHOICES_UNDERSTAND, default=False
    )
    understand_alt = models.BooleanField(
        verbose_understand, choices=BOOL_CHOICES_UNDERSTAND, default=False
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="convention"
    )
    officer1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conv_off1",
        verbose_name="Officer Signature",
    )
    officer2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="conv_off2",
        verbose_name="Officer Signature",
    )
    signature_del = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name"
    )
    signature_alt = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name"
    )
    signature_o1 = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name"
    )
    signature_o2 = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name"
    )
    approved_o1 = models.BooleanField(
        "Officer Approved", choices=BOOL_CHOICES, default=False
    )
    approved_o2 = models.BooleanField(
        "Officer Approved", choices=BOOL_CHOICES, default=False
    )

    def __str__(self):
        return f"Convention Process for {self.chapter}"


class PledgeProcess(Process, EmailSignalMixin):
    pledges = models.ManyToManyField(Pledge, related_name="process", blank=True)
    invoice = models.PositiveIntegerField("Invoice Number", default=999999999)
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="pledge_process"
    )

    def __str__(self):
        return f"Pledge Process for {self.chapter}"

    def sync_invoice(self, request, invoice_number):
        """
        This will sync with quickbooks
        """
        client = get_quickbooks_client()
        chapter = self.chapter
        chapter_name = chapter.name
        customer = Customer.query(
            select=f"SELECT * FROM Customer WHERE CompanyName LIKE '{chapter_name} chapter%'",
            qb=client,
        )
        if customer:
            customer = customer[0]
        else:
            messages.add_message(
                request,
                messages.ERROR,
                f"Quickbooks Customer matching name: '{chapter_name} Chapter...' not found",
            )
            return
        invoice, linenumber_count = invoice_search(invoice_number, customer, client)
        count = self.pledges.count()
        line = create_line(count, linenumber_count, name="P1A", client=client)
        invoice.Line.append(line)
        memo = "Pledges: " + ", ".join(
            self.pledges.values_list("user__name", flat=True)
        )
        old_memo = invoice.CustomerMemo.value
        memo = old_memo + "\n" + memo if old_memo else memo
        # Maximum 1000 chars
        memo = memo[0:999]
        invoice.CustomerMemo.value = memo
        invoice.DeliveryInfo = None
        invoice_obj = invoice.save(qb=client)
        attachment_path = self.generate_invoice_attachment(file_obj=True)
        attachment = Attachable()
        attachable_ref = AttachableRef()
        attachable_ref.EntityRef = invoice.to_ref()
        attachable_ref.IncludeOnSend = True
        attachment.AttachableRef.append(attachable_ref)
        attachment.FileName = attachment_path.name
        attachment._FilePath = str(attachment_path.absolute())
        attachment.ContentType = "text/csv"
        attachment.save(qb=client)
        if attachment_path.exists():
            attachment_path.unlink()  # Delete the file when we are done
        return invoice_obj.DocNumber

    def generate_invoice_attachment(self, response=None, file_obj=False):
        columns = [
            "Submission Date",
            "Title",
            "Legal First Name",
            "Full Middle Name",
            "Last Name",
            "Nickname",
            "School E-mail",
            "Mobile Number:",
            "Chapter",
            "Major",
            "Expected date of graduation",
        ]
        chapter = self.chapter.name
        todays_date = datetime.datetime.now().date().strftime("%Y%m%d")
        filename = f"{chapter}_{todays_date}_pledges_invoice.csv"
        if response is not None:
            pledge_file = response
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            out = None
        else:
            pledge_file = io.StringIO()
            pledge_mail = MIMEBase("application", "csv")
            pledge_mail.add_header(
                "Content-Disposition", "attachment", filename=filename
            )
        writer = csv.DictWriter(pledge_file, fieldnames=columns)
        writer.writeheader()
        for pledge in self.pledges.all():
            row = {
                "Submission Date": pledge.created,
                "Title": pledge.user.title,
                "Legal First Name": pledge.user.first_name,
                "Full Middle Name": pledge.user.middle_name,
                "Last Name": pledge.user.last_name,
                "Nickname": pledge.user.nickname,
                "School E-mail": pledge.user.email_school,
                "Mobile Number:": pledge.user.phone_number,
                "Chapter": self.chapter,
                "Major": pledge.user.major,
                "Expected date of graduation": pledge.user.graduation_year,
            }
            writer.writerow(row)
        if response is None and not file_obj:
            pledge_mail.set_payload(pledge_file.getvalue())
            out = pledge_mail
        else:
            filepath = Path(r"exports/" + filename)
            with open(filepath, mode="w", newline="") as f:
                print(pledge_file.getvalue(), file=f)
            out = filepath
        return out

    def generate_blackbaud_update(self, response=None):
        columns = [
            "Submission Date",
            "Title",
            "Legal First Name",
            "Full Middle Name",
            "Last Name",
            "Suffix (such as Jr., III)",
            "Nickname",
            "Parent / Guardian Name",
            "School E-mail",
            "Personal Email",
            "Mobile Number:",
            "Home Phone",
            "Street Address",
            "City",
            "Permanent Home Address State/Province",
            "Zip Code 2",
            "Country",
            "Birth Date:",
            "Place of Birth",
            "School Name",
            "Abbrev",
            "Chapter",
            "Major",
            "Expected date of graduation",
            "College degrees already received",
            "Theta Tau Relatives",
            "Of which Greek Letter Honor Societies are you a member?",
            "Of which technical societies are you a member?",
            "Of which fraternities are you a member?",
            "Which? (Other college)",
            "Have you ever been expelled from any college?",
            "If yes, please explain. (College explain)",
            "If yes, please explain. (Crime explain)",
            "Loyalty",
            "not honor",
            "accountable",
            "life",
            "unlawful",
            "unlawful_org",
            "brotherhood",
            "engineering",
            "engineering practice",
            "payment",
            "attendance",
            "harmless",
            "Alumni Association",
            "Honest",
            "/Signature/",
            "Date Signed - Today's Date",
        ]
        chapter = self.chapter.name
        chapter_abr = self.chapter.greek
        todays_date = datetime.datetime.now().date().strftime("%Y%m%d")
        filename = f"{chapter}_{todays_date}_pledges.csv"
        out = response
        if response is not None:
            pledge_file = response
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
        else:
            pledge_file = io.StringIO()
            pledge_mail = MIMEBase("application", "csv")
            pledge_mail.add_header(
                "Content-Disposition", "attachment", filename=filename
            )
        writer = csv.DictWriter(pledge_file, fieldnames=columns)
        writer.writeheader()
        for pledge in self.pledges.all():
            city, state, zipcode, country = "", "", "", ""
            if pledge.user.address and pledge.user.address.locality:
                city = pledge.user.address.locality.name
                state = pledge.user.address.locality.state.code
                zipcode = pledge.user.address.locality.postal_code
                country = pledge.user.address.locality.state.country
            expelled_college = False
            if pledge.explain_expelled_college:
                expelled_college = True
            row = {
                "Submission Date": pledge.created,
                "Title": pledge.user.title,
                "Legal First Name": pledge.user.first_name,
                "Full Middle Name": pledge.user.middle_name,
                "Last Name": pledge.user.last_name,
                "Suffix (such as Jr., III)": pledge.user.suffix,
                "Nickname": pledge.user.nickname,
                "Parent / Guardian Name": pledge.parent_name,
                "Parent / Guardian Email": pledge.parent_email,
                "School E-mail": pledge.user.email_school,
                "Personal Email": pledge.user.email,
                "Mobile Number:": pledge.user.phone_number,
                "Home Phone": "",
                "Street Address": pledge.user.address,
                "City": city,
                "Permanent Home Address State/Province": state,
                "Zip Code 2": zipcode,
                "Country": country,
                "Birth Date:": pledge.user.birth_date,
                "Place of Birth": pledge.birth_place,
                "School Name": self.chapter.school,
                "Abbrev": chapter_abr,
                "Chapter": self.chapter,
                "Major": pledge.user.major,
                "Expected date of graduation": pledge.user.graduation_year,
                "College degrees already received": pledge.other_degrees,
                "Theta Tau Relatives": pledge.relative_members,
                "Of which Greek Letter Honor Societies are you a member?": pledge.other_greeks,
                "Of which technical societies are you a member?": pledge.other_tech,
                "Of which fraternities are you a member?": pledge.other_frat,
                "Which? (Other college)": pledge.other_college,
                "Have you ever been expelled from any college?": expelled_college,
                "If yes, please explain. (College explain)": pledge.explain_expelled_college,
                "If yes, please explain. (Crime explain)": pledge.explain_crime,
                "Loyalty": pledge.loyalty,
                "not honor": pledge.not_honor,
                "accountable": pledge.accountable,
                "life": pledge.life,
                "unlawful": pledge.unlawful,
                "unlawful_org": pledge.unlawful_org,
                "brotherhood": pledge.brotherhood,
                "engineering": pledge.engineering,
                "engineering practice": pledge.engineering_grad,
                "payment": pledge.payment,
                "attendance": pledge.attendance,
                "harmless": pledge.harmless,
                "Alumni Association": pledge.alumni,
                "Honest": pledge.honest,
                "/Signature/": pledge.signature,
                "Date Signed - Today's Date": pledge.created,
            }
            writer.writerow(row)
        if response is None:
            pledge_mail.set_payload(pledge_file.getvalue())
            out = pledge_mail
        return out


class OSM(Process, YearTermModel, EmailSignalMixin):
    BOOL_CHOICES = ((True, "Approve"), (False, "Deny"))
    meeting_date = models.DateField(default=timezone.now, validators=[no_future])
    nominate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="osm",
        verbose_name="OSM Nomination",
    )
    verbose_selection_process = (
        "How was the Chapter Outstanding Student Member chosen?"
        + " What process was used to select them?"
    )
    selection_process = models.TextField(verbose_selection_process)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, related_name="osm")
    officer1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="osm_off1",
        verbose_name="Officer Signature",
    )
    officer2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="osm_off2",
        verbose_name="Officer Signature",
    )
    approved_o1 = models.BooleanField(
        "Officer Approved", choices=BOOL_CHOICES, default=False
    )
    approved_o2 = models.BooleanField(
        "Officer Approved", choices=BOOL_CHOICES, default=False
    )

    def __str__(self):
        return f"Outstanding Student Member {self.nominate} for {self.chapter}"


def get_discipline_upload_path(instance, filename):
    if hasattr(instance, "attachment"):
        instance = instance.process
    if not hasattr(instance, "chapter"):
        chapter = instance.user.chapter
    else:
        chapter = instance.chapter
    return os.path.join(
        "discipline",
        f"{chapter.slug}",
        f"{instance.user.id}",
        f"{chapter.slug}_{instance.user.id}_{filename}",
    )


class DisciplinaryProcess(Process, TimeStampedModel, EmailSignalMixin):
    """
    Restart:
    https://stackoverflow.com/questions/61136760/allowing-users-to-select-which-flow-to-roll-back-to-django-viewflow
    Delay:
    https://stackoverflow.com/questions/31658996/viewflow-io-implementing-a-queue-task
    """

    BOOL_CHOICES = ((True, "Yes"), (False, "No"))

    class METHODS(EnumClass):
        postal = ("postal", "Postal Mail")
        email = ("email", "Email")
        text = ("text", "Text Message")
        social = ("social", "Social Media")
        phone = ("phone", "Phone Call")
        person = ("person", "In Person")
        chat = ("chat", "Chat Message")

    class REASONS(EnumClass):
        waived = ("waived", "Accused Waived Right to Trial")
        rescheduled = ("rescheduled", "Rescheduled")

    class PUNISHMENT(EnumClass):
        expelled = ("expelled", "Expelled")
        suspended = ("suspended", "Suspended")

    class PROCESS(EnumClass):
        process = ("process", "Accept and Process")
        accept = ("accept", "Accept With No Action")
        reject = ("reject", "Reject")
        not_review = ("not_review", "Not Reviewed")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Name of Accused",
        on_delete=models.CASCADE,
        related_name="discipline",
    )
    address = AddressField(
        verbose_name=_("Mailing Address of Accused"),
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="discipline"
    )
    charges = models.TextField(
        help_text="Please specify which section of the PPM the member is "
        "accused of violating."
    )
    verbose_resolve = (
        "Did chapter officers try to resolve the problem through "
        "private discussion with the brother?"
    )
    resolve = models.BooleanField(verbose_resolve, choices=BOOL_CHOICES, default=False)
    verbose_advisor = (
        "Was the chapter alumni adviser involved in trying to resolve this problem?"
    )
    advisor = models.BooleanField(verbose_advisor, choices=BOOL_CHOICES, default=False)
    advisor_name = models.CharField(
        "If yes, alumni advisor name",
        max_length=200,
        blank=True,
        null=True,
    )
    verbose_faculty = (
        "Was a campus/faculty adviser involved in trying to resolve this problem?"
    )
    faculty = models.BooleanField(verbose_faculty, choices=BOOL_CHOICES, default=False)
    faculty_name = models.CharField(
        "If yes, campus/faculty adviser name",
        max_length=200,
        blank=True,
        null=True,
    )
    verbose_financial = (
        "Is a simple collections action (for financial delinquency) "
        "better suited as a resolution to this issue?"
    )
    financial = models.BooleanField(
        verbose_financial, choices=BOOL_CHOICES, default=False
    )
    charges_filed = models.DateField(
        "Charges filed by majority vote at a chapter meeting on date",
        default=timezone.now,
        validators=[no_future],
    )
    notify_date = models.DateField(
        "Accused first notified of charges on date",
        default=timezone.now,
        validators=[no_future],
    )
    notify_method = MultiSelectField(choices=[x.value for x in METHODS], max_length=500)
    trial_date = models.DateField(
        "Trial scheduled for date",
        default=timezone.now,
    )
    charging_letter = models.FileField(
        upload_to=get_discipline_upload_path,
        help_text="Please attach a copy of the charging letter that was sent to the member.",
    )
    verbose_take = "Did the trial take place as planned?"
    take = models.BooleanField(verbose_take, choices=BOOL_CHOICES, default=False)
    verbose_why_take = "Why did the trial not take place?"
    why_take = models.CharField(
        verbose_why_take,
        max_length=100,
        blank=True,
        null=True,
        choices=[x.value for x in REASONS],
    )
    send_ec_date = models.DateField(blank=True, null=True)
    rescheduled_date = models.DateField(
        "When will the new trial be held?",
        default=timezone.now,
    )
    verbose_attend = "Did the accused attend the trial and defend?"
    attend = models.BooleanField(verbose_attend, choices=BOOL_CHOICES, default=False)
    verbose_guilty = (
        "Was the accused found guilty of the charges by a 4/5 majority of the jury?"
    )
    guilty = models.BooleanField(verbose_guilty, choices=BOOL_CHOICES, default=False)
    verbose_notify_results = (
        "Did the chapter notify the member by mail/email of the results of the trial?"
    )
    notify_results = models.BooleanField(
        verbose_notify_results, choices=BOOL_CHOICES, default=False
    )
    notify_results_date = models.DateField(
        "On what date was the member notified of the results of the trial?",
        default=timezone.now,
        validators=[no_future],
    )
    verbose_punishment = "What was the punishment agreed to by the chapter?"
    punishment = models.CharField(
        verbose_punishment,
        max_length=100,
        default="suspended",
        choices=[x.value for x in PUNISHMENT],
    )
    suspension_end = models.DateField(
        "If suspended, when will this member’s suspension end?",
        default=timezone.now,
    )
    verbose_punishment_other = (
        "What other punishments, if any, were agreed to by the chapter?"
    )
    punishment_other = models.TextField(verbose_punishment_other, blank=True, null=True)
    verbose_collect_items = (
        "If the member was suspended pending expulsion, did the chapter collect "
        "and receive the member’s badge, shingle and/or other Theta Tau property?"
    )
    collect_items = models.BooleanField(
        verbose_collect_items, choices=BOOL_CHOICES, default=False
    )
    minutes = models.FileField(
        upload_to=get_discipline_upload_path,
        blank=True,
        null=True,
        help_text="Please attach a copy of the minutes from the meeting "
        "where the trial was held.",
    )
    results_letter = models.FileField(
        upload_to=get_discipline_upload_path,
        blank=True,
        null=True,
        help_text="Please attach a copy of the letter you sent to the member "
        "informing them of the outcome of the trial.",
    )
    ed_process = models.CharField(
        "Executive Director Review",
        max_length=10,
        choices=[x.value for x in PROCESS],
        default="not_review",
        blank=True,
        null=True,
    )
    ed_notes = models.TextField(
        "Executive Director Review Notes", blank=True, null=True
    )
    ec_approval = models.BooleanField(
        "Executive Council Outcome",
        choices=(
            (True, "Outcome approved by EC"),
            (False, "Outcome Rejected by EC"),
            ("", "Not reviewed yet"),
        ),
        default="",
        blank=True,
        null=True,
    )
    ec_notes = models.TextField("Executive Council Review Notes", blank=True, null=True)
    # Letter of outcome of trial
    outcome_letter = models.FileField(
        upload_to=get_discipline_upload_path, blank=True, null=True
    )
    # Letter at the end of whole process
    final_letter = models.FileField(
        upload_to=get_discipline_upload_path, blank=True, null=True
    )

    def __str__(self):
        return f"Disciplinary Process for {self.user} from {self.chapter}"

    def forms_pdf(self):
        from forms.forms import DisciplinaryForm1, DisciplinaryForm2

        all_fields = (
            DisciplinaryForm1._meta.fields[:] + DisciplinaryForm2._meta.fields[:]
        )
        all_fields.extend(["ed_process", "ed_notes", "ec_approval", "ec_notes"])
        info = {}
        for field in all_fields:
            field_obj = self._meta.get_field(field)
            if field == "user":
                info[field_obj.verbose_name] = self.user
                continue
            try:
                info[field_obj.verbose_name] = self._get_FIELD_display(field_obj)
            except TypeError:
                info[field_obj.verbose_name] = field_obj.value_to_string(self)
        forms = render_to_pdf(
            "forms/disciplinary_form_pdf.html",
            context={"info": info},
        )
        return forms

    def get_all_files(self):
        files = []
        for file_field in [
            "charging_letter",
            "minutes",
            "results_letter",
            "outcome_letter",
            "final_letter",
        ]:
            value = getattr(self, file_field)
            if value.name:
                files.append(value)
        for attach in self.attachments.all():
            files.append(attach.file)
        return files


class DisciplinaryAttachment(models.Model):
    attachment = True  # This allows reuse of get_discipline_upload_path
    file = models.FileField(
        upload_to=get_discipline_upload_path,
        help_text="Please attach a copy of the letter you sent to the member "
        "informing them of the outcome of the trial.",
    )
    process = models.ForeignKey(
        DisciplinaryProcess, on_delete=models.CASCADE, related_name="attachments"
    )


class CollectionReferral(TimeStampedModel, EmailSignalMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Indebted Member",
        on_delete=models.CASCADE,
        related_name="collection",
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    balance_due = MoneyField(max_digits=19, decimal_places=4, default_currency="USD")
    ledger_sheet = models.FileField(upload_to=get_discipline_upload_path)

    def __str__(self):
        return f"Collection referral for {self.user}"


def get_resign_upload_path(instance, filename):
    return os.path.join(
        "submissions",
        "resign",
        f"{instance.user.chapter.slug}_{instance.user.id}_{filename}",
    )


class ResignationProcess(Process, EmailSignalMixin):
    BOOL_CHOICES = ((True, "Yes"), (False, "No"))
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resignation",
        null=True,
        blank=True,
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="resignations"
    )
    letter = models.FileField("Resignation Letter", upload_to=get_resign_upload_path)
    verbose_resign = _(
        "For reasons which I deem good and sufficient, I wish to resign as a "
        "member of Theta Tau Fraternity."
    )
    resign = models.BooleanField(verbose_resign, choices=BOOL_CHOICES, default=False)
    verbose_secrets = _(
        "I recognize that I am under a solemn obligation never to reveal any of "
        "the Secrets of the Fraternity, and I reaffirm my previous obligation "
        "never to reveal any secrets of Theta Tau Fraternity."
    )
    secrets = models.BooleanField(verbose_secrets, choices=BOOL_CHOICES, default=False)
    verbose_expel = _(
        "I understand that I will be treated as an expelled member of Theta Tau "
        "and can only rejoin the fraternity by special petition to the Grand Regent."
    )
    expel = models.BooleanField(verbose_expel, choices=BOOL_CHOICES, default=False)
    verbose_return_evidence = _(
        "I have or will returned all evidence of my membership in Theta Tau "
        "and all insignia previously possessed by me and now in my possession, "
        "and certify that evidence and insignia not returned to the chapter "
        "herewith has been lost or misplaced and if hereafter located will be returned."
    )
    return_evidence = models.BooleanField(
        verbose_return_evidence, choices=BOOL_CHOICES, default=False
    )
    verbose_obligation = _(
        "I consent to the retention by my chapter and by Theta Tau Fraternity "
        "of all fees and dues heretofore paid by me while a member of said "
        "chapter and said Fraternity hereby releasing them from any and all "
        "obligations to me henceforth and forever."
    )
    obligation = models.BooleanField(
        verbose_obligation, choices=BOOL_CHOICES, default=False
    )
    verbose_fee = _(
        "I have or will submit the Resignation Processing Fee to the chapter."
    )
    fee = models.BooleanField(verbose_fee, choices=BOOL_CHOICES, default=False)
    signature = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name"
    )
    verbose_good_standing = _("The member is in good standing of Theta Tau.")
    good_standing = models.BooleanField(
        verbose_good_standing, choices=BOOL_CHOICES, default=False
    )
    verbose_returned = "Did the member return all evidence of membership in Theta Tau?"
    returned = models.BooleanField(
        verbose_returned, choices=BOOL_CHOICES, default=False
    )
    verbose_financial = _("Member has no current financial obligation to the chapter.")
    financial = models.BooleanField(
        verbose_financial, choices=BOOL_CHOICES, default=False
    )
    verbose_fee_paid = _(
        "Member submitted the Resignation Processing Fee to the chapter."
    )
    fee_paid = models.BooleanField(
        verbose_fee_paid, choices=BOOL_CHOICES, default=False
    )
    officer1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resign_off1",
        verbose_name="Officer Signature",
    )
    officer2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resign_off2",
        verbose_name="Officer Signature",
    )
    signature_o1 = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name"
    )
    signature_o2 = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name"
    )
    approved_o1 = models.BooleanField(
        "Officer Approved", choices=BOOL_CHOICES, default=False
    )
    approved_o2 = models.BooleanField(
        "Officer Approved", choices=BOOL_CHOICES, default=False
    )
    approved_exec = models.BooleanField("Executive Director Approved", default=False)
    exec_comments = models.TextField(_("If rejecting, please explain why."), blank=True)

    def __str__(self):
        return f"Resignation {self.user} from {self.chapter}"


class ReturnStudent(Process, EmailSignalMixin):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="return_form",
        null=True,
        blank=True,
    )
    verbose_reason = _("""Reasons member requests transfer to student member status.""")
    reason = models.TextField(verbose_reason)
    verbose_financial = _(
        """I understand that semiannual dues obligation for the current semester
        must be met if student member status
        is resumed on or before the semiannual dues deadline (November 1/March 15)."""
    )
    financial = models.BooleanField(verbose_financial, default=False)
    verbose_debt = _(
        """This member has paid previous fraternity debt to the chapter."""
    )
    debt = models.BooleanField(verbose_debt, default=False)
    approved_exec = models.BooleanField("Executive Director Approved", default=False)
    exec_comments = models.TextField(_("If rejecting, please explain why."), blank=True)
    verbose_vote = _(
        """The status change for the member was approved by a four-fifths favorable vote of the chapter."""
    )
    vote = models.BooleanField(verbose_vote, default=False)

    def __str__(self):
        return f"Return Student {self.user}"


def get_chapter_bylaws_upload_path(instance, filename):
    return os.path.join(
        "submissions",
        "bylaws",
        f"{instance.chapter.slug}_{instance.created.strftime('%Y%m%d')}_{filename}",
    )


class Bylaws(TimeStampedModel, EmailSignalMixin):
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="bylaws"
    )
    bylaws = models.FileField(upload_to=get_chapter_bylaws_upload_path)
    changes = models.TextField(_("Summary of Changes"))

    def __str__(self):
        return f"Bylaws for {self.chapter}"
