import os
import datetime
from enum import Enum
from django.db import models, transaction
from django.db.utils import IntegrityError
from django.core.validators import MaxValueValidator
from django.conf import settings
from django.utils import timezone
from core.models import TimeStampedModel, YearTermModel, gd_storage
from django.utils.translation import gettext_lazy as _
from multiselectfield import MultiSelectField
from core.models import forever, CHAPTER_ROLES_CHOICES
from users.models import User, UserStatusChange
from chapters.models import Chapter
from tasks.models import TaskChapter


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
        'media', 'pledge_programs', instance.chapter.slug,
        f"{instance.year}_{instance.term}_{filename}")


class PledgeProgram(YearTermModel, TimeStampedModel):
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
    manual = models.CharField(
        max_length=10,
        choices=[x.value for x in MANUALS]
    )
    other_manual = models.FileField(
        upload_to=get_pledge_program_upload_path,
        storage=gd_storage, null=True, blank=True)

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


class RiskManagement(YearTermModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="risk_form")
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
