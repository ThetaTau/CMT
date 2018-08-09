from enum import Enum
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from django.core.validators import MaxValueValidator
from django.conf import settings
from django.utils import timezone
from core.models import TimeStampedModel
from django.utils.translation import gettext_lazy as _
from users.models import User
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
    date_graduation = models.DateTimeField(default=timezone.now)
    date = models.DateTimeField(default=timezone.now)
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
    task = GenericRelation(TaskChapter)

    def __str__(self):
        return f"{self.user} initiated on {self.date}"

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
    date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user} depledged on {self.date}"


def forever():
    return timezone.now() + timezone.timedelta(days=1000000)


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
                             related_name="change")
    reason = models.CharField(
        max_length=10,
        choices=[x.value for x in REASONS]
    )

    degree = models.CharField(
        max_length=4,
        choices=[x.value for x in DEGREES]
    )
    date_start = models.DateTimeField(default=timezone.now)
    date_end = models.DateTimeField(default=forever, blank=True)
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
