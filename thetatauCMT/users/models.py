import datetime
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator,\
    RegexValidator
from address.models import AddressField
from core.models import StartEndModel, YearTermModel, TODAY_END, CHAPTER_OFFICER, \
    ALL_OFFICERS_CHOICES, TimeStampedModel, NATIONAL_OFFICER, COL_OFFICER_ALIGN
from chapters.models import Chapter


class User(AbstractUser):
    class Meta:
        ordering = ['last_name', ]
    # First Name and Last Name do not cover name patterns
    # around the globe.
    name = models.CharField(_('Member Name'), blank=True, max_length=255)
    modified = models.DateTimeField(auto_now=True)
    badge_number = models.PositiveIntegerField(default=999999999)
    user_id = models.CharField(max_length=20,
                               unique=True,
                               help_text="Combination of badge number and chapter abbr, eg. X1311")
    major = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=100, blank=True)
    employer_position = models.CharField(max_length=100, blank=True)
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
        return self.name

    @property
    def current_chapter(self):
        # This allows for national officers to change their chapter
        # without actually changing their chapter
        chapter = self.chapter
        if self.groups.filter(name='natoff').exists():
            if self.altered_chapter.all():
                chapter = self.altered_chapter.first().chapter
        return chapter

    def get_absolute_url(self):
        return reverse('users:detail',
                       kwargs={'username': self.username})

    def get_current_status(self):
        return self.status.filter(start__lte=TODAY_END,
                                  end__gte=TODAY_END).first()

    def get_current_role(self):
        return self.roles.filter(end__gte=TODAY_END).first()

    def get_current_roles(self):
        return self.roles.filter(end__gte=TODAY_END)

    def chapter_officer(self):
        """
        An member can have multiple roles need to see if any are officer
        :return: Bool if officer, set of officer roles
        """
        role_objs = self.get_current_roles()
        officer_roles = {}
        current_roles = {}
        if role_objs is not None:
            for role_obj in role_objs:
                role_name = role_obj.role.lower()
                if role_name in COL_OFFICER_ALIGN:
                    role_name = COL_OFFICER_ALIGN[role_name]
                current_roles.add(role_name)
            # officer = not current_roles.isdisjoint(CHAPTER_OFFICER)
            officer_roles = CHAPTER_OFFICER & current_roles
        return officer_roles

    @property
    def is_national_officer_group(self):
        return self.groups.filter(name='natoff').exists()

    @property
    def is_chapter_officer_group(self):
        return self.groups.filter(name='officer').exists()

    def is_national_officer(self):
        role_objs = self.get_current_roles()
        officer = False
        officer_roles = {}
        current_roles = {}
        if role_objs is not None:
            for role_obj in role_objs:
                role_name = role_obj.role.lower()
                if role_name in COL_OFFICER_ALIGN:
                    role_name = COL_OFFICER_ALIGN[role_name]
                current_roles.add(role_name)
            officer = not current_roles.isdisjoint(NATIONAL_OFFICER)
            officer_roles = NATIONAL_OFFICER & current_roles
        return officer

    @property
    def is_officer(self):
        return len(self.chapter_officer()) > 0 or self.is_national_officer()

    def is_officer_group(self):
        groups = ['officer', 'natoff']
        user_groups = self.groups.values_list("name", flat=True)
        return set(groups).intersection(set(user_groups))


class UserAlterChapter(models.Model):
    '''
    This is used for altering things for natoffs
    ie. when a natoff wants to check things for another chapter
    '''
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="altered_chapter")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                default=1,
                                related_name="altered_member")


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


class UserStatusChange(StartEndModel, TimeStampedModel):
    STATUS = [
        ('alumni', 'alumni'),
        ('alumnipend', 'alumni pending'),
        ('active', 'active'),
        ('activepend', 'active pending'),
        ('pnm', 'prospective'),
        ('away', 'away'),
        ('depledge', 'depledge'),
    ]
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="status")
    status = models.CharField(
        max_length=10,
        choices=STATUS
    )

    def __str__(self):
        return self.status


class UserRoleChange(StartEndModel, TimeStampedModel):
    ROLES = ALL_OFFICERS_CHOICES
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="roles")
    role = models.CharField(max_length=50,
                            choices=ROLES)

    def __str__(self):
        return self.role

    def save(self, *args, **kwargs):
        off_group, created = Group.objects.get_or_create(name='officer')
        super().save(*args, **kwargs)
        self.clean_group_role()
        # Need to check current role, b/c user could have multiple
        current_role = self.user.get_current_role()
        if current_role:
            off_group.user_set.add(self.user)
        else:
            self.user.groups.remove(off_group)
            off_group.user_set.remove(self.user)
            self.user.save()

    def clean_group_role(self):
        """
        This cleans up the officer group when the role is updated
        This will leave a user in officer group until a replacement is elected
        :return:
        """
        off_group, created = Group.objects.get_or_create(name='officer')
        previuos_users = UserRoleChange.get_role_members(self.user, self.role)
        for user_role in previuos_users:
            user_role.user.groups.remove(off_group)
            off_group.user_set.remove(user_role.user)
            user_role.user.save()

    @classmethod
    def get_role_members(cls, user, role):
        return cls.objects.filter(
            role=role,
            user__chapter=user.current_chapter,
            end__lte=TODAY_END)

    @classmethod
    def get_current_roles(cls, user):
        return cls.objects.filter(
            user__chapter=user.current_chapter,
            start__lte=TODAY_END, end__gte=TODAY_END).order_by('user__last_name')


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
