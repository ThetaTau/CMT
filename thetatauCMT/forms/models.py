import datetime
import os
from enum import Enum
from django.db import models, transaction
from django.db.utils import IntegrityError
from django.contrib.auth.models import Group
from django.core.validators import MaxValueValidator, RegexValidator
from django.conf import settings
from django.utils import timezone
from core.models import TimeStampedModel, YearTermModel, validate_year
from django.utils.translation import gettext_lazy as _
from address.models import AddressField
from multiselectfield import MultiSelectField
from core.models import forever, CHAPTER_ROLES_CHOICES,\
    academic_encompass_start_end_date
from users.models import User, UserStatusChange
from chapters.models import Chapter, ChapterCurricula
from tasks.models import TaskChapter
from submissions.models import Submission


class MultiSelectField(MultiSelectField):
    # Not Django 2.0+ ready yet, https://github.com/goinnn/django-multiselectfield/issues/74
    def value_to_string(self, obj):
        value = self.value_from_object(obj)
        return self.get_prep_value(value)


class Badge(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=50)
    description = models.CharField(max_length=500)
    cost = models.DecimalField(default=0, decimal_places=2,
                               max_digits=7,
                               help_text="Cost of item.")

    def __str__(self):
        return f"{self.name}; ${self.cost}"


class Guard(models.Model):
    ONE_LETTER = 1
    TWO_LETTER = 2
    NUM_LETTERS = (
        (ONE_LETTER, 'one'),
        (TWO_LETTER, 'two'),
    )
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=50)
    letters = models.IntegerField(default=ONE_LETTER, choices=NUM_LETTERS)
    description = models.CharField(max_length=500)
    cost = models.DecimalField(default=0, decimal_places=2,
                               max_digits=7,
                               help_text="Cost of item.")

    def __str__(self):
        return f"{self.name}; ${self.cost}"


class PledgeForm(TimeStampedModel):
    class Meta:
        unique_together = ('name', 'email',)
    name = models.CharField(_('Pledge Name'), max_length=255)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                related_name="pledge_forms")
    email = models.EmailField(_('email address'), blank=True)


def get_pledge_program_upload_path(instance, filename):
    return os.path.join(
        'submissions', 'pledge_programs',
        f"{instance.chapter.slug}_{instance.year}_{instance.term}_{filename}")


class PledgeProgram(YearTermModel, TimeStampedModel):
    BOOL_CHOICES = ((True, 'Yes'), (False, 'No'))
    class Meta:
        unique_together = ('chapter', 'year', 'term', )

    class MANUALS(Enum):
        basic = ('basic', 'Basic')
        nontrad = ('nontrad', 'Non-traditional')
        standard = ('standard', 'Standard')
        other = ('other', 'Other')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[1]

    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                related_name="pledge_programs")
    verbose_remote = "Will your new member education be run remotely?"
    remote = models.BooleanField(verbose_remote, choices=BOOL_CHOICES, default=False)
    verbose_complete = "When do you anticipate completing new member education?"
    date_complete = models.DateField(verbose_complete, default=timezone.now)
    verbose_initiation = "When do you plan to hold initiations?"
    date_initiation = models.DateField(verbose_initiation, default=timezone.now)
    manual = models.CharField(
        max_length=10,
        choices=[x.value for x in MANUALS]
    )
    other_manual = models.FileField(
        upload_to=get_pledge_program_upload_path,
        null=True, blank=True)

    @classmethod
    def form_chapter_term(cls, chapter):
        """
        If the current term is the spring, the form could have been submitted
        in the fall of last year.
        :param chapter:
        :return: form for current year, semester for chapter
        """
        program_fa = None
        if YearTermModel.current_term() == 'sp':
            program_fa = cls.objects.filter(
                chapter=chapter,
                year=YearTermModel.current_year() - 1,
                term='fa',
            ).first()
        program = cls.objects.filter(
            chapter=chapter,
            year=YearTermModel.current_year(),
            term=YearTermModel.current_term(),
            ).first()
        return program or program_fa


class Initiation(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name="initiation")
    date_graduation = models.DateField(default=timezone.now)
    date = models.DateField("Initiation Date", default=timezone.now)
    roll = models.PositiveIntegerField(default=999999999)
    gpa = models.FloatField()
    test_a = models.IntegerField(validators=[MaxValueValidator(100)])
    test_b = models.IntegerField(validators=[MaxValueValidator(100)])
    badge = models.ForeignKey(Badge, on_delete=models.SET_NULL,
                              related_name="initiation",
                              null=True)
    guard = models.ForeignKey(Guard, on_delete=models.SET_NULL,
                              related_name="initiation",
                              null=True)
    # task = GenericRelation(TaskChapter)  We are currently not using this

    def __str__(self):
        return f"{self.user} initiated on {self.date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Need to adjust old status pnm, save new status active
        new_user_id = f"{self.user.chapter.greek}{self.roll}"
        if self.user.user_id != new_user_id:
            self.user.badge_number = self.roll
            self.user.user_id = new_user_id
            try:
                with transaction.atomic():
                    self.user.save()
            except IntegrityError as e:
                print("User ALREADY EXISTS", str(e))
        try:
            pnm = self.user.status.get(status='pnm')
        except UserStatusChange.DoesNotExist:
            print(f"There was no pledge status for user {self.user}")
            UserStatusChange(
                user=self.user,
                status='pnm',
                created=self.created,
                start=self.date - datetime.timedelta(days=120),
                end=self.date,
            ).save()
        except UserStatusChange.MultipleObjectsReturned:
            self.user.status.filter(status='pnm').order_by('created').last().delete()
            pnm = self.user.status.filter(status='pnm').last()
        pnm.end = self.date
        pnm.created = self.created
        pnm.save()
        actives = self.user.status.filter(status='active')
        for active in actives:
            active.delete()
        alumnis = self.user.status.filter(status='alumni')
        for alumni in alumnis:
            alumni.delete()
        activepends = self.user.status.filter(status='activepend')
        if activepends:
            activepend = activepends[0]
            activepend.start = self.date
            activepend.created = self.created
            activepend.end = forever()
            activepend.save()
            for activepend in activepends[1:]:
                activepend.delete()
        else:
            UserStatusChange(
                user=self.user,
                created=self.created,
                status='activepend',
                start=self.date,
                end=forever(),
            ).save()

    def chapter_initiations(self, chapter):
        result = self.objects.filter(user__chapter=chapter)
        return result


class Depledge(TimeStampedModel):
    class REASONS(Enum):
        volunteer = ('volunteer', 'Voluntarily decided not to continue')
        time = ('time', 'Too much time required')
        grades = ('grades', 'Poor grades')
        interest = ('interest', 'Lost interest')
        vote = ('vote', 'Negative Chapter Vote')
        withdrew = ('withdrew', 'Withdrew from Engineering/University')
        transfer = ('transfer', 'Transferring to another school')
        other = ('other', 'Other')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[1]

    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name="depledge")
    reason = models.CharField(
        max_length=10,
        choices=[x.value for x in REASONS]
    )
    date = models.DateField("Depledge Date", default=timezone.now)

    def __str__(self):
        return f"{self.user} depledged on {self.date}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Need to adjust old status pnm, save new status depledge
        try:
            pnm = self.user.status.get(status='pnm')
        except UserStatusChange.DoesNotExist:
            print(f"There was no pledge status for user {self.user}")
            UserStatusChange(
                user=self.user,
                status='pnm',
                created=self.created,
                start=self.date - datetime.timedelta(days=120),
                end=self.date,
            ).save()
        else:
            pnm.end = self.date
            pnm.created = self.created
            pnm.save()
        actives = self.user.status.filter(status='active')
        for active in actives:
            active.delete()
        alumnis = self.user.status.filter(status='alumni')
        for alumni in alumnis:
            alumni.delete()
        depledges = self.user.status.filter(status='depledge')
        if depledges:
            depledge = depledges[0]
            depledge.start = self.date
            depledge.created = self.created
            depledge.end = forever()
            depledge.save()
            for depledge in depledges[1:]:
                depledge.delete()
        else:
            UserStatusChange(
                user=self.user,
                status='depledge',
                created=self.created,
                start=self.date,
                end=forever(),
            ).save()


class StatusChange(TimeStampedModel):
    class REASONS(Enum):
        graduate = ('graduate', 'Member is graduating')  # Graduated from school
        coop = ('coop', 'Member is going on CoOp or Study abroad')  # Co-Op/Internship
        military = ('military', 'Member is being deployed')  # Called to Active/Reserve Military Duty
        withdraw = ('withdraw', 'Member is withdrawing from school')  # Withdrawing from school
        transfer = ('transfer', 'Member is transferring to another school')  # Transferring to another school

        @classmethod
        def get_value(cls, member):
            return cls[member].value[1]

    class DEGREES(Enum):
        BS = ('bs', 'Bachelor of Science')
        MS = ('ms', 'Master of Science')
        MBA = ('mba', 'Master of Business Administration')
        PhD = ('phd', 'Doctor of Philosophy')
        BA = ('ba', 'Bachelor of Arts')
        MA = ('ma', 'Master of Arts')
        ME = ('me', 'Master of Engineering')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[1]

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="status_changes")
    reason = models.CharField(
        max_length=10,
        choices=[x.value for x in REASONS]
    )

    degree = models.CharField(
        max_length=4,
        choices=[x.value for x in DEGREES]
    )
    date_start = models.DateField("Start Date", default=timezone.now)
    date_end = models.DateField("End Date", default=forever, blank=True)
    employer = models.CharField(max_length=200)
    miles = models.PositiveIntegerField(
        default=0,
        help_text="Miles from campus.")
    email_work = models.EmailField(_('email address'), blank=True)
    new_school = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                   default=None, related_name="transfers",
                                   null=True, blank=True)
    # task = GenericRelation(TaskChapter)

    def __str__(self):
        return f"{self.user} {self.reason} on {self.date_start}"

    def save_only(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # if graduate, withdraw, transfer
        # Need to adjust old status active, save new status alumni
        # if coop, military
        # Need to adjust old status active, save new status away
        active = self.user.status.order_by('-end')\
            .filter(status='active').first()
        if not active:
            print(f"There was no active status for user {self.user}")
            UserStatusChange(
                user=self.user,
                status='active',
                created=self.created,
                start=self.date_start - datetime.timedelta(days=365),
                end=self.date_start,
            ).save()
        else:
            active.end = self.date_start
            active.created = self.created
            active.save()
        if self.reason in ['graduate', 'withdraw', 'transfer']:
            alumnis = self.user.status.filter(status='alumni')
            for alumni in alumnis:
                alumni.delete()
            alumnipends = self.user.status.filter(status='alumnipend')
            if alumnipends:
                alumnipend = alumnipends[0]
                alumnipend.start = self.date_start
                alumnipend.end = forever()
                alumnipend.created = self.created
                alumnipend.save()
                for alumnipend in alumnipends[1:]:
                    alumnipend.delete()
            else:
                UserStatusChange(
                    user=self.user,
                    created=self.created,
                    status='alumnipend',
                    start=self.date_start,
                    end=forever(),
                ).save()
        else:
            alumnis = self.user.status.filter(status='alumni')
            for alumni in alumnis:
                alumni.delete()
            aways = self.user.status.filter(status='away')
            if aways:
                away = aways[0]
                away.start = self.date_start
                away.end = self.date_end
                away.created = self.created
                away.save()
                for away in aways[1:]:
                    away.delete()
            else:
                UserStatusChange(
                    user=self.user,
                    created=self.created,
                    status='away',
                    start=self.date_start,
                    end=self.date_end,
                ).save()


def get_chapter_report_upload_path(instance, filename):
    return os.path.join(
        'submissions', 'chapter_report',
        f"{instance.chapter.slug}_{instance.year}_{instance.term}_{filename}")


class ChapterReport(YearTermModel, TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="chapter_form")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                related_name="info")
    report = models.FileField(upload_to=get_chapter_report_upload_path)


class RiskManagement(YearTermModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="risk_form")
    role = models.CharField(max_length=50)
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE,
                                   related_name="risk_management_forms",
                                   null=True)
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
    terms_agreement = models.BooleanField()
    typed_name = models.CharField(max_length=255)

    @staticmethod
    def risk_forms_chapter_year(chapter, year):
        chapter_officers = chapter.get_current_officers_council()
        start, end = academic_encompass_start_end_date(year)
        return RiskManagement.objects.filter(
            user__in=chapter_officers, date__gte=start, date__lte=end)

    @staticmethod
    def risk_forms_year(year):
        if str(year) == str(datetime.datetime.now().year):
            return RiskManagement.risk_forms_current_year()
        else:
            return RiskManagement.risk_forms_previous_year(year)

    @staticmethod
    def risk_forms_current_year():
        """
        Current year, all those officers who are currently in list of officers
        :return:
        """
        off_group, _ = Group.objects.get_or_create(name='officer')
        chapter_officers = off_group.user_set.all()
        start, end = academic_encompass_start_end_date()
        return RiskManagement.objects.filter(
            user__in=chapter_officers, date__gte=start, date__lte=end)

    @staticmethod
    def risk_forms_previous_year(year):
        """
        Previous officers are those who had role at time of submission
        :param year:
        :return:
        """
        off_group, _ = Group.objects.get_or_create(name='officer')
        start, end = academic_encompass_start_end_date(year)
        return RiskManagement.objects.filter(
            date__gte=start, date__lte=end)

    @staticmethod
    def user_signed_this_year(user):
        start, end = academic_encompass_start_end_date()
        signed_before = user.risk_form.filter(date__gte=start, date__lte=end)
        return signed_before


class Audit(YearTermModel, TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="audit_form")
    dues_member = models.FloatField("Member Dues")
    dues_pledge = models.FloatField("Potential New Member Pledging Fees/Dues")
    frequency = models.CharField(
        "What is the frequency of member dues",
        max_length=10,
        choices=[('month', 'month'), ('semester', 'semester'),
                 ('quarter', 'quarter'), ('year', 'year'), ]
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
        choices=[('None', 'None')] + CHAPTER_ROLES_CHOICES)
    agreement = models.BooleanField()


class Pledge(TimeStampedModel):
    BOOL_CHOICES = ((True, 'Yes'), (False, 'No'))
    signature = models.CharField(
        max_length=255, help_text="Please sign using your proper/legal name")
    title = models.CharField(
        max_length=5,
        choices=[('mr', 'Mr.'), ('miss', 'Miss'), ('ms', 'Ms'), ('mrs', 'Mrs'), ])
    first_name = models.CharField(_('Legal First Name'), max_length=30)
    middle_name = models.CharField(_('Full Middle Name'), max_length=30, blank=True)
    last_name = models.CharField(_('Legal Last Name'), max_length=30)
    suffix = models.CharField(_('Suffix (such as Jr., III)'), max_length=10, blank=True)
    nickname = models.CharField(
        max_length=30, blank=True,
        help_text="If different than your first name - eg Buddy, Skip, or Mike. Do NOT indicate 'pledge names'")
    parent_name = models.CharField(_('Parent / Guardian Name'), max_length=60)
    email_school = models.EmailField(
        _('School Email'),
        help_text="We will send an acknowledgement message. (ends in .edu)")
    email_personal = models.EmailField(
        _('Personal Email'),
        help_text="Personal email address like @gmail.com, @yahoo.com, @outlook.com, etc")
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone_mobile = models.CharField(
        _('Mobile Phone'), validators=[phone_regex], max_length=17,
        help_text="Format: 9999999999 no spaces, dashes, etc.")
    phone_home = models.CharField(
        _('Home Phone'), validators=[phone_regex], max_length=17,
        help_text="Format: 9999999999 no spaces, dashes, etc.")
    address = AddressField(on_delete=models.PROTECT)
    birth_date = models.DateField()
    birth_place = models.CharField(
        _('Place of Birth'), max_length=50,
        help_text=_("City and state or province is sufficient"))
    school_name = models.ForeignKey(Chapter, to_field='school',
                                    on_delete=models.CASCADE,
                                    related_name="pledge_forms_full")
    major = models.ForeignKey(ChapterCurricula, on_delete=models.CASCADE,
                              related_name="pledges")
    grad_date_year = models.IntegerField(
        _('Expected date of graduation'), validators=[validate_year],
        help_text="The year closest to your expected date of graduation in YYYY format.")
    other_degrees = models.CharField(
        _('College degrees already received'), max_length=60, blank=True,
        help_text="Name of Major/Field of that Degree. If none, leave blank")
    relative_members = models.CharField(
        _('Indicate the names of any relatives you have who are members of Theta Tau below'),
        max_length=60, blank=True,
        help_text="Include relationship, chapter, and graduation year, if known. If none, leave blank")
    other_greeks = models.CharField(
        _('Of which Greek Letter Honor Societies are you a member?'),
        max_length=60, blank=True, help_text="If none, leave blank")
    other_tech = models.CharField(
        _('Of which technical societies are you a member?'),
        max_length=60, blank=True, help_text="If none, leave blank")
    other_frat = models.CharField(
        _('Of which fraternities are you a member?'),
        max_length=60, blank=True, help_text="Other than Theta Tau -- If no other, leave blank")
    other_college = models.CharField(
        _('Which? (Other college(s))'), max_length=60, blank=True)
    explain_expelled_org = models.TextField(
        _('If yes, please explain.'), blank=True)
    explain_expelled_college = models.TextField(
        _('If yes, please explain.'), blank=True)
    explain_crime = models.TextField(
        _('If yes, please explain.'), blank=True)
    verbose_loyalty = _("""The purpose of Theta Tau shall be to develop and maintain a high standard of professional interest among its members and to unite them in a strong bond of fraternal fellowship. The members are pledged to help one another professionally and personally in a practical way, as students and as alumni, advising as to opportunities for service and advancement, warning against unethical practices and persons. Do you believe that such a fraternity is entitled to your continued support and loyalty?""")
    loyalty = models.BooleanField(verbose_loyalty, choices=BOOL_CHOICES, default=False)
    verbose_not_honor = _("""Theta Tau is a fraternity, not an honor society. It aims to elect no one to any class of membership solely in recognition of his scholastic or professional achievements. Do you subscribe to this doctrine?""")
    not_honor = models.BooleanField(verbose_not_honor, choices=BOOL_CHOICES, default=False)
    verbose_accountable = _("""Do you understand, if you become a member of Theta Tau, that the other members will have the right to hold you accountable for your conduct? Do you further understand that the Fraternity has Risk Management policies (hazing, alcohol, etc) with which you are expected to comply and to which you should expect others to comply?""")
    accountable = models.BooleanField(verbose_accountable, choices=BOOL_CHOICES, default=False)
    verbose_life = _("""When you assume the oaths or obligations required during initiation, will you agree that they are binding on the member for life?""")
    life = models.BooleanField(verbose_life, choices=BOOL_CHOICES, default=False)
    verbose_unlawful = _("""Do you promise that you will not permit the use of a Theta Tau headquarters or meeting place for unlawful purposes?""")
    unlawful = models.BooleanField(verbose_unlawful, choices=BOOL_CHOICES, default=False)
    verbose_unlawful_org = _("""This Fraternity requires of its initiates that they shall not be members of any sect or organization which teaches or practices activities in violation of the laws of the state or the nation. Do you subscribe to this requirement?""")
    unlawful_org = models.BooleanField(verbose_unlawful_org, choices=BOOL_CHOICES, default=False)
    verbose_brotherhood = _("""The strength of the Fraternity depends largely on the character of its members and the close and loyal friendship uniting them. Do you realize you have no right to join if you do not act on this belief?""")
    brotherhood = models.BooleanField(verbose_brotherhood, choices=BOOL_CHOICES, default=False)
    verbose_engineering = _("""Theta Tau is an engineering fraternity whose student membership is limited to those regularly enrolled in a course leading to a degree in an approved engineering curriculum. Members of other fraternities that restrict their membership to any, or several engineering curricula are generally not eligible to Theta Tau, nor may our members join such fraternities. Engineering honor societies such as Tau Beta Pi, Eta Kappa Nu, etc., are not included in this classification. Do you fully understand and subscribe to that policy?""")
    engineering = models.BooleanField(verbose_engineering, choices=BOOL_CHOICES, default=False)
    verbose_engineering_grad = _("""Is it your intention to practice engineering after graduation?""")
    engineering_grad = models.BooleanField(verbose_engineering_grad, choices=BOOL_CHOICES, default=False)
    verbose_payment = _("""The Fraternity has a right to demand from you prompt payment of bills. Do you understand, and are you ready to accept, the financial obligations of becoming a member?""")
    payment = models.BooleanField(verbose_payment, choices=BOOL_CHOICES, default=False)
    verbose_attendance = _("""The Fraternity has a right to demand from you regular attendance at meetings and faithful performance of duties entrusted to you. Are you ready to accept such obligations?""")
    attendance = models.BooleanField(verbose_attendance, choices=BOOL_CHOICES, default=False)
    verbose_harmless = _("""Do you agree hereby to fully and completely release, discharge, and hold harmless the Chapter, House Corporation, Theta Tau (the national Fraternity), and their respective members, officers, agents, and any other entity whose liability is derivative by or through said released parties from all past, present and future claims, causes of action and liabilities of any nature whatsoever, regardless of the cause of the damage or loss, and including, but not limited to, claims and losses covered by insurance, claims and damages for property, for personal injury, for premises liability, for torts of any nature, and claims for compensatory damages, consequential damages or punitive/exemplary damages? Your affirmative answer binds you, under covenant, not to sue any of the previously named entities.""")
    harmless = models.BooleanField(verbose_harmless, choices=BOOL_CHOICES, default=False)
    verbose_alumni = _("""As an alumnus, you should join with other alumni in the formation and support of alumni clubs or associations. Furthermore, on October 15th of each year, celebrations are held throughout the country to recall the founding of our Fraternity and to honor the Founders. Members of Theta Tau are encouraged to send some form of greeting to their chapters on or about October 15th. If several members are located in the same vicinity they could gather for an informal meeting. Will you endeavor to do these things, as circumstances permit, after you are initiated into Theta Tau?""")
    alumni = models.BooleanField(verbose_alumni, choices=BOOL_CHOICES, default=False)
    verbose_honest = _("""My answers to these questions are my honest and sincere convictions.""")
    honest = models.BooleanField(verbose_honest, choices=BOOL_CHOICES, default=False)
