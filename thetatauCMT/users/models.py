import datetime
from django.contrib.auth.models import AbstractUser, Group
from django.db import models
from django.contrib.auth.models import UserManager
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from address.models import AddressField
from core.models import (
    StartEndModel,
    YearTermModel,
    TODAY_END,
    CHAPTER_OFFICER,
    ALL_ROLES_CHOICES,
    TimeStampedModel,
    NATIONAL_OFFICER,
    COL_OFFICER_ALIGN,
    CHAPTER_OFFICER_CHOICES,
    CHAPTER_ROLES,
    NAT_OFFICERS,
    COUNCIL,
)
from chapters.models import Chapter


class CustomUserManager(UserManager):
    def create_superuser(self, email, password, **extra_fields):
        chapter = Chapter.objects.first()
        if chapter is None:
            # this would happen on first install; make a default test region/chapter
            from regions.models import Region

            region = Region.objects.first()
            if region is None:
                region = Region(name="Test Region").save()
            chapter = Chapter(name="Test Chapter", region=region).save()
        extra_fields.setdefault("chapter", chapter)
        super().create_superuser(email=email, password=password, **extra_fields)


class User(AbstractUser):
    class Meta:
        ordering = [
            "last_name",
        ]

    objects = CustomUserManager()
    # First Name and Last Name do not cover name patterns
    # around the globe.
    name = models.CharField(_("Member Name"), blank=True, max_length=255)
    modified = models.DateTimeField(auto_now=True)
    badge_number = models.PositiveIntegerField(default=999999999)
    title = models.CharField(_("Title"), blank=True, max_length=255)
    user_id = models.CharField(
        max_length=20,
        unique=True,
        help_text="Combination of badge number and chapter abbr, eg. X1311",
    )
    major = models.CharField(max_length=100, blank=True)
    employer = models.CharField(max_length=100, blank=True)
    employer_position = models.CharField(max_length=100, blank=True)
    graduation_year = models.PositiveIntegerField(
        default=datetime.datetime.now().year,
        validators=[
            MinValueValidator(1950),
            MaxValueValidator(datetime.datetime.now().year + 10),
        ],
        help_text="Use the following format: YYYY",
    )
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        help_text="Format: 9999999999 no spaces, dashes, etc.",
    )
    address = AddressField(on_delete=models.SET_NULL, blank=True, null=True,)
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, default=1, related_name="members"
    )

    def save(self, *args, **kwargs):
        if not self.id:
            # Newly created object, so set user_id
            # Combination of badge number and chapter abbr, eg. X1311
            chapter = kwargs.get("chapter", self.chapter)
            self.user_id = f"{chapter.greek}{self.badge_number}"
        if self.name == "":
            self.name = self.first_name + " " + self.last_name
        if self.username == "":
            self.username = self.email
        super(User, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    @property
    def current_chapter(self):
        # This allows for national officers to change their chapter
        # without actually changing their chapter
        chapter = self.chapter
        if self.groups.filter(name="natoff").exists():
            if self.altered.all():
                chapter = self.altered.first().chapter
        return chapter

    def get_absolute_url(self):
        return reverse("users:detail")

    @property
    def clean_user_id(self):
        """
        Pledges should not have greek letter in user_id only badge_number
        """
        if self.current_status == "pnm":
            return self.badge_number
        return self.user_id

    @property
    def current_status(self):
        return str(self.get_current_status())

    @current_status.setter
    def current_status(self, val):
        self._current_status = val

    def get_current_status(self):
        if hasattr(self, "_current_status"):
            return self._current_status
        return self.status.filter(start__lte=TODAY_END, end__gte=TODAY_END).first()

    @property
    def role(self):
        return self.get_current_role()

    @role.setter
    def role(self, val):
        self._role = val

    def get_current_role(self):
        if hasattr(self, "_role"):
            return self._role
        return self.roles.filter(end__gte=TODAY_END).first()

    def get_current_roles(self):
        role_objs = self.roles.filter(end__gte=TODAY_END)
        current_roles = set()
        if role_objs is not None:
            for role_obj in role_objs:
                role_name = role_obj.role.lower()
                if role_name in COL_OFFICER_ALIGN:
                    role_name = COL_OFFICER_ALIGN[role_name]
                current_roles.add(role_name)
        return current_roles

    def get_user_role_level(self):
        current_roles = self.get_current_roles()
        if COUNCIL & current_roles:
            return "council", COUNCIL & current_roles
        elif set(NAT_OFFICERS) & current_roles:
            return "nat_off", set(NAT_OFFICERS) & current_roles
        elif self.chapter_officer():
            return "convention", self.chapter_officer()
        else:
            return "", current_roles

    def chapter_officer(self, altered=True):
        """
        An member can have multiple roles need to see if any are officer
        :return: Bool if officer, set of officer roles
        """
        current_roles = self.get_current_roles()
        # officer = not current_roles.isdisjoint(CHAPTER_OFFICER)
        officer_roles = CHAPTER_OFFICER & current_roles
        if self.is_national_officer_group:
            if altered and self.altered.all():
                new_role = self.altered.first().role
                if new_role is not None and new_role != "":
                    officer_roles.add(new_role)
        return officer_roles

    @property
    def is_national_officer_group(self):
        return self.groups.filter(name="natoff").exists()

    @property
    def is_chapter_officer_group(self):
        return self.groups.filter(name="officer").exists()

    @property
    def is_officer_group(self):
        return self.is_national_officer_group or self.is_chapter_officer_group

    def is_national_officer(self):
        current_roles = self.get_current_roles()
        officer_roles = set(NAT_OFFICERS) & current_roles
        return officer_roles

    def is_council_officer(self):
        current_roles = self.get_current_roles()
        officer_roles = COUNCIL & current_roles
        return officer_roles

    @property
    def is_officer(self):
        return len(self.chapter_officer()) > 0 or len(self.is_national_officer()) > 0

    def is_officer_group(self):
        groups = ["officer", "natoff"]
        user_groups = self.groups.values_list("name", flat=True)
        return set(groups).intersection(set(user_groups))


class UserAlter(models.Model):
    """
    This is used for altering things for natoffs
    ie. when a natoff wants to check things for another chapter
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="altered"
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, default=1, related_name="altered_member"
    )
    ROLES = CHAPTER_OFFICER_CHOICES + [(None, "------------")]
    role = models.CharField(max_length=50, choices=ROLES, null=True)


class UserSemesterServiceHours(YearTermModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="service_hours"
    )
    service_hours = models.FloatField(default=0)


class UserSemesterGPA(YearTermModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gpas"
    )
    gpa = models.FloatField()


class UserStatusChange(StartEndModel, TimeStampedModel):
    STATUS = [
        ("alumni", "alumni"),
        ("alumnipend", "alumni pending"),
        ("active", "active"),
        ("activepend", "active pending"),
        ("pnm", "prospective"),
        ("away", "away"),
        ("depledge", "depledge"),
        ("advisor", "advisor"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="status"
    )
    status = models.CharField(max_length=10, choices=STATUS)

    def __str__(self):
        return self.status


class UserRoleChange(StartEndModel, TimeStampedModel):
    ROLES = ALL_ROLES_CHOICES
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="roles"
    )
    role = models.CharField(max_length=50, choices=ROLES)

    def __str__(self):
        return self.role

    def save(self, *args, **kwargs):
        off_group, _ = Group.objects.get_or_create(name="officer")
        nat_group, _ = Group.objects.get_or_create(name="natoff")
        super().save(*args, **kwargs)
        self.clean_group_role()
        # Need to check current role, b/c user could have multiple
        current_role = self.user.get_current_role()
        if current_role:
            off_group.user_set.add(self.user)
            if current_role.role in NAT_OFFICERS:
                nat_group.user_set.add(self.user)
        else:
            self.user.groups.remove(off_group)
            self.user.groups.remove(nat_group)
            off_group.user_set.remove(self.user)
            nat_group.user_set.remove(self.user)
            self.user.save()

    def clean_group_role(self):
        """
        This cleans up the officer group when the role is updated
        This will leave a user in officer group until a replacement is elected
        :return:
        """
        off_group, created = Group.objects.get_or_create(name="officer")
        previuos_users = UserRoleChange.get_role_members(self.user, self.role)
        officer_users = off_group.user_set.all()
        for user_role in previuos_users:
            if user_role.user in officer_users:
                if not user_role.user.is_officer:
                    user_role.user.groups.remove(off_group)
                    off_group.user_set.remove(user_role.user)
                    user_role.user.save()

    @classmethod
    def get_role_members(cls, user, role):
        return cls.objects.filter(
            role=role, user__chapter=user.current_chapter, end__lte=TODAY_END
        )

    @classmethod
    def get_current_roles(cls, user):
        return cls.objects.filter(
            role__in=CHAPTER_ROLES,
            user__chapter=user.current_chapter,
            start__lte=TODAY_END,
            end__gte=TODAY_END,
        ).order_by("user__last_name")

    @classmethod
    def get_current_natoff(cls):
        return cls.objects.filter(
            role__in=NAT_OFFICERS, start__lte=TODAY_END, end__gte=TODAY_END
        ).order_by("user__last_name")


class UserOrgParticipate(StartEndModel):
    TYPES = [
        ("pro", "Professional"),
        ("tec", "Technical"),
        ("hon", "Honor"),
        ("oth", "Other"),
    ]
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orgs"
    )
    org_name = models.CharField(max_length=50)
    type = models.CharField(max_length=3, choices=TYPES)
    officer = models.BooleanField(default=False)
