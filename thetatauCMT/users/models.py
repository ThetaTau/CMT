import datetime
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator,\
    RegexValidator
from address.models import AddressField
from core.models import StartEndModel, YearTermModel
from chapters.models import Chapter


class User(AbstractUser):
    # First Name and Last Name do not cover name patterns
    # around the globe.
    name = models.CharField(_('Name of User'), blank=True, max_length=255)
    modified = models.DateTimeField(auto_now=True)
    badge_number = models.PositiveIntegerField(default=999999999)
    user_id = models.CharField(max_length=20,
                               unique=True,
                               help_text="Combination of badge number and chapter abbr, eg. X1311")
    major = models.CharField(max_length=100, blank=True)
    graduation_year = models.PositiveIntegerField(
        default=datetime.datetime.now().year,
        validators=[
            MinValueValidator(1950),
            MaxValueValidator(datetime.datetime.now().year + 10)],
        help_text="Use the following format: YYYY")
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17, blank=True)
    address = AddressField(on_delete=models.SET_NULL, blank=True, null=True, unique=True)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                default=1,
                                related_name="members")

    def save(self, *args, **kwargs):
        if not self.id:
            # Newly created object, so set user_id
            # Combination of badge number and chapter abbr, eg. X1311
            self.user_id = f"{self.chapter.greek}{self.badge_number}"
        super(User, self).save(*args, **kwargs)

    def __str__(self):
        return self.username

    def get_absolute_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.username})


class UserSemesterServiceHours(YearTermModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="service_hours")
    service_hours = models.FloatField(default=0)


class UserSemesterGPA(YearTermModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="gpas")
    gpa = models.FloatField()


class UserStatusChange(StartEndModel):
    STATUS = [
        ('alumni', 'alumni'),
        ('active', 'active'),
        ('pnm', 'prospective'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="status")
    status = models.CharField(
        max_length=7,
        choices=STATUS
    )


class UserRoleChange(StartEndModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="roles")
    role = models.CharField(max_length=50)


class UserOrgParticipate(StartEndModel):
    TYPES = [
        ('pro', 'Professional'),
        ('tec', 'Technical'),
        ('hon', 'Honor'),
        ('oth', 'Other'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="orgs")
    org_name = models.CharField(max_length=50)
    type = models.CharField(
        max_length=3,
        choices=TYPES
    )
    officer = models.BooleanField(default=False)
