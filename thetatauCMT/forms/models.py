import datetime
from enum import Enum
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator
from django.conf import settings
from django.utils import timezone
from core.models import TimeStampedModel, YearTermModel, forever
from django.utils.translation import gettext_lazy as _
from core.models import forever
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


class Initiation(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name="initiation")
    date_graduation = models.DateField(default=timezone.now)
    date = models.DateField(default=timezone.now)
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
            self.user.save()
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
        try:
            active = self.user.status.get(status='active')
        except UserStatusChange.DoesNotExist:
            UserStatusChange(
                user=self.user,
                created=self.created,
                status='active',
                start=self.date,
                end=self.date_graduation,
            ).save()
        else:
            active.start = self.date
            active.created = self.created
            active.end = self.date_graduation
            active.save()

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
            return cls[member].value[0]

    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                related_name="depledge")
    reason = models.CharField(
        max_length=10,
        choices=[x.value for x in REASONS]
    )
    date = models.DateField(default=timezone.now)

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
        withdrew = ('withdraw', 'Member is withdrawing from school')  # Withdrawing from school
        transfer = ('transfer', 'Member is transferring to another school')  # Transferring to another school

        @classmethod
        def get_value(cls, member):
            return cls[member].value[0]

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
            return cls[member].value[0]

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
    date_start = models.DateField(default=timezone.now)
    date_end = models.DateField(default=forever, blank=True)
    employer = models.CharField(max_length=200)
    miles = models.PositiveIntegerField(
        default=0,
        help_text="Miles from campus.")
    email_work = models.EmailField(_('email address'), blank=True)
    new_school = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                   default=1, related_name="transfers")
    task = GenericRelation(TaskChapter)

    def __str__(self):
        return f"{self.user} {self.reason} on {self.date_start}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # if graduate, withdraw, transfer
        # Need to adjust old status active, save new status alumni
        # if coop, military
        # Need to adjust old status active, save new status away
        try:
            active = self.user.status.order_by('-end')\
                .filter(status='active').first()
        except UserStatusChange.DoesNotExist:
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
            try:
                alumni = self.user.status.get(status='alumni')
            except UserStatusChange.DoesNotExist:
                UserStatusChange(
                    user=self.user,
                    created=self.created,
                    status='alumni',
                    start=self.date_start,
                    end=forever(),
                ).save()
            else:
                alumni.start = self.date_start
                alumni.end = forever()
                alumni.created = self.created
                alumni.save()
        else:
            try:
                away = self.user.status.get(status='away')
            except UserStatusChange.DoesNotExist:
                UserStatusChange(
                    user=self.user,
                    created=self.created,
                    status='away',
                    start=self.date_start,
                    end=self.date_end,
                ).save()
            else:
                away.start = self.date_start
                away.end = self.date_end
                away.created = self.created
                away.save()


class RiskManagement(YearTermModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="risk_form")
    date = models.DateTimeField(default=timezone.now)
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
