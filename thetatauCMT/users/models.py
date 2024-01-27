import datetime
from django.contrib.auth.models import AbstractUser, Group
from django.contrib.postgres.fields import ArrayField
from django_userforeignkey.models.fields import UserForeignKey
from django.db import models, IntegrityError
from django.contrib.auth.models import UserManager
from django.urls import reverse
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from model_utils.fields import MonitorField
from address.models import AddressField
from multiselectfield import MultiSelectField
from email_signals.models import EmailSignalMixin
from simple_history.models import HistoricalRecords
from viewflow.models import Process
from core.models import (
    StartEndModel,
    YearTermModel,
    forever,
    current_year,
    current_year_plus_10,
    TODAY,
    TOMORROW,
    TODAY_END,
    CHAPTER_OFFICER,
    ALL_ROLES_CHOICES,
    TimeStampedModel,
    COL_OFFICER_ALIGN,
    CHAPTER_OFFICER_CHOICES,
    CHAPTER_ROLES,
    NAT_OFFICERS,
    COUNCIL,
    EnumClass,
)
from chapters.models import Chapter, ChapterCurricula


class CustomUserManager(UserManager):
    def create_superuser(self, email, password, **extra_fields):
        chapter = Chapter.objects.first()
        if chapter is None:
            # this would happen on first install; make a default test region/chapter
            from regions.models import Region

            region = Region.objects.first()
            if region is None:
                Region(name="Test Region").save()
                region = Region.objects.first()
            Chapter(name="Test Chapter", region=region).save()
            chapter = Chapter.objects.first()
        extra_fields.setdefault("chapter", chapter)
        super().create_superuser(email=email, password=password, **extra_fields)


class User(AbstractUser, EmailSignalMixin):
    class EMERGENCY_RELATIONSHIP(EnumClass):
        parent = ("parent", "Parent")
        guardian = ("guardian", "Guardian")
        grandparent = ("grandparent", "Grandparent")
        partner = ("partner", "Spouse/Partner")
        sibling = ("sibling", "Sibling (over 18)")
        other = ("other", "Other relative")
        friend = ("friend", "Friend")

    class DEGREES(EnumClass):
        BS = ("bs", "Bachelor of Science")
        MS = ("ms", "Master of Science")
        MBA = ("mba", "Master of Business Administration")
        PhD = ("phd", "Doctor of Philosophy")
        BA = ("ba", "Bachelor of Arts")
        MA = ("ma", "Master of Arts")
        ME = ("me", "Master of Engineering")
        NONE = ("none", "None")

    class Meta:
        ordering = [
            "last_name",
        ]

    class ReportBuilder:
        extra = (
            "is_officer",
            "is_advisor",
        )

    objects = CustomUserManager()
    # First Name and Last Name do not cover name patterns
    # around the globe.
    name = models.CharField(_("Member Name"), blank=True, max_length=255)
    middle_name = models.CharField(_("Full Middle Name"), max_length=30, blank=True)
    maiden_name = models.CharField(_("Maiden Name"), max_length=150, blank=True)
    suffix = models.CharField(_("Suffix (such as Jr., III)"), max_length=10, blank=True)
    preferred_pronouns = models.CharField(
        _("Preferred Pronouns"),
        max_length=255,
        blank=True,
        null=True,
        help_text="Pronouns are the part of speech used to refer to someone in the third person. We want to know how to respectfully refer to you.",
    )
    preferred_name = models.CharField(
        _("Preferred Name"),
        max_length=255,
        blank=True,
        null=True,
        help_text="Preferred First Name - eg my first name is Kevin but I go by my middle name Henry.",
    )
    nickname = models.CharField(
        max_length=30,
        blank=True,
        help_text="Other than first name and preferred first name - eg Bud, Skip, Frank The Tank, Etc. Do NOT indicate 'pledge names'",
    )
    email_school = models.EmailField(
        _("School Email"),
        blank=True,
        help_text="We will send an acknowledgement message. (ends in .edu)",
    )
    modified = models.DateTimeField(auto_now=True)
    badge_number = models.PositiveIntegerField(default=999999999)
    title = models.CharField(
        _("Title"),
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
    degree = models.CharField(
        max_length=4, choices=[x.value for x in DEGREES], default="bs"
    )
    major = models.ForeignKey(
        ChapterCurricula,
        on_delete=models.SET_NULL,
        related_name="user",
        blank=True,
        null=True,
    )
    employer = models.CharField(max_length=100, blank=True)
    employer_changed = MonitorField(monitor="employer")
    employer_position = models.CharField(max_length=100, blank=True, default="")
    employer_address = AddressField(
        on_delete=models.SET_NULL, blank=True, null=True, related_name="employer"
    )
    emergency_first_name = models.CharField(
        _("Emergency Contact first name"), max_length=30, blank=True, null=True
    )
    emergency_middle_name = models.CharField(
        _("Emergency Contact Middle Name"), max_length=30, blank=True, null=True
    )
    emergency_last_name = models.CharField(
        _("Emergency Contact last name"), max_length=150, blank=True, null=True
    )
    emergency_nickname = models.CharField(
        _("Emergency Contact nickname name"), max_length=30, blank=True, null=True
    )
    phone_regex = RegexValidator(
        regex=r"^\+?1?\d{9,15}$",
        message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
    )
    emergency_phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True,
        help_text="Format: 9999999999 no spaces, dashes, etc.",
    )
    emergency_relation = models.CharField(
        max_length=20,
        choices=[x.value for x in EMERGENCY_RELATIONSHIP],
        blank=True,
        null=True,
    )
    graduation_year = models.PositiveIntegerField(
        default=current_year,
        validators=[
            MinValueValidator(1900),
            MaxValueValidator(current_year_plus_10),
        ],
        help_text="Use the following format: YYYY",
    )
    phone_number = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        help_text="Format: 9999999999 no spaces, dashes, etc.",
    )
    birth_date = models.DateField(default=datetime.date(year=1904, month=10, day=15))
    address = AddressField(
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    address_changed = MonitorField(monitor="address")
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, default=1, related_name="members"
    )
    deceased = models.BooleanField(default=False)
    deceased_changed = MonitorField(monitor="deceased", default=forever)
    deceased_date = models.DateField(
        blank=True,
        null=True,
    )
    no_contact = models.BooleanField(default=False)
    charter = models.BooleanField(default=False, help_text="Charter member")
    ##### DENORMALIZED FIELDS #####
    current_status = models.CharField(max_length=10)
    current_roles = ArrayField(models.CharField(max_length=50), blank=True, null=True)
    officer = models.BooleanField(default=False)
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        suffix = f" {self.suffix}" if self.suffix else ""
        if self.name == "":
            self.name = f"{self.first_name} {self.middle_name} {self.last_name}{suffix}"
        if self.preferred_name is not None:
            self.name = f"{self.preferred_name} {self.last_name}{suffix}"
        if self.username == "":
            self.username = self.email
        super(User, self).save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_name_with_details(self):
        major = self.major if self.major else ""
        return f"{self.name} graduated: {self.graduation_year} {self.degree} {major}"

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

    @classmethod
    def next_pledge_number(cls):
        pledge_numbers = list(
            cls.objects.filter(
                badge_number__gte=2_000_000, badge_number__lte=3_000_000
            ).values_list("badge_number", flat=True)
        )
        if not pledge_numbers:
            pledge_numbers.append(1_999_999)
        pledge_number = max(pledge_numbers) + 1
        return pledge_number

    def reset_status(self):
        # Need to find the previous status before the current one
        #   set that status as now current
        statuses = list(UserStatusChange.objects.filter(user=self).order_by("start"))
        previous_status = statuses[-2]
        self.set_current_status(previous_status.status)

    def set_current_status(
        self, status, created=None, start=None, end=None, current=True
    ):
        if start is None:
            start = TODAY
        if created is None:
            created = TODAY
        if end is None:
            end = forever()
        if type(end) is datetime.datetime:
            end = end.date()
        if type(start) is datetime.datetime:
            start = start.date()
        if isinstance(status, UserStatusChange):
            status = status.status
        if end > TODAY >= start:
            if current:
                # If the current status is being set.
                current_status = self.status.filter(
                    start__lte=TODAY_END, end__gte=TODAY_END
                ).all()
                for old_status in current_status:
                    old_status.end = start - datetime.timedelta(days=1)
                    old_status.save()
        if status is None:
            # if alumni, set back alumni, else nonmember
            status = "alumni"
            alumni = UserStatusChange.objects.filter(user=self, status="alumni")
            if not alumni:
                status = "nonmember"
        if self.chapter.candidate_chapter:
            status = {"active": "activeCC", "alumni": "alumniCC"}.get(status, status)
        UserStatusChange(
            user=self,
            created=created,
            status=status,
            start=start,
            end=end,
        ).save()

    def get_roles_on_date(self, date):
        return self.roles.filter(end__gte=date, start__lte=date)

    def get_officer_role_on_date(self, date):
        roles = self.get_roles_on_date(date)
        return roles.filter(role__in=CHAPTER_OFFICER).first()

    def chapter_officer(self, altered=True):
        """
        An member can have multiple roles need to see if any are officer
        :return: Bool if officer, set of officer roles
        """
        current_roles = set(self.current_roles) if self.current_roles else set()
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
        current_roles = set(self.current_roles) if self.current_roles else set()
        officer_roles = set(NAT_OFFICERS) & set(current_roles)
        return officer_roles

    def is_council_officer(self):
        current_roles = set(self.current_roles) if self.current_roles else set()
        officer_roles = COUNCIL & set(current_roles)
        return officer_roles

    @property
    def is_officer(self):
        return len(self.chapter_officer()) > 0 or len(self.is_national_officer()) > 0

    @property
    def is_advisor(self):
        return self.current_status == "advisor"

    @classmethod
    def fix_badge_numbers(cls, reader, test=False, sep="<br>"):
        updated_users = []
        missing = []
        updated = []
        for count, row in enumerate(reader):
            id = row["id"].strip()
            if not id:
                continue
            try:
                user = User.objects.get(id=id)
            except User.DoesNotExist:
                missing.append(id)
                continue
            else:
                updated.append(user)
            badge_number = row["correct"]
            updated_users.append({"id": user.id, "badge_number": badge_number})
        if not test:
            message = ""
            if missing:
                message += f"Could not find users: {missing}{sep}"
            cls.objects.bulk_update(
                [User(**kv) for kv in updated_users],
                [
                    "badge_number",
                ],
            )
            if updated:
                message += f"Updated members: {updated}"
            return message


class UserDemographic(models.Model):
    BOOL_CHOICES = ((None, ""), (True, "Yes"), (False, "No"))

    class GENDER(EnumClass):
        not_listed = ("not_listed", "An identity not listed (write-in)")
        agender = ("agender", "Agender")
        cisgender = ("cisgender", "Cisgender")
        female = ("female", "Female")
        genderqueer = ("genderqueer", "Genderqueer/Gender non-conforming")
        intersex = ("intersex", "Intersex")
        male = ("male", "Male")
        nonbinary = ("nonbinary", "Nonbinary")
        no_answer = ("no_answer", "Prefer not to answer")
        transgender = ("transgender", "Transgender")

    class SEXUAL(EnumClass):
        asexual = ("asexual", "Asexual")
        bisexual = ("bisexual", "Bisexual")
        not_listed = ("not_listed", "An identity not listed (write-in)")
        heterosexual = ("heterosexual", "Heterosexual / straight")
        homosexual = ("homosexual", "Homosexual / gay / lesbian")
        no_answer = ("no_answer", "Prefer not to answer")
        queer = ("queer", "Queer")

    class RACIAL(EnumClass):
        asian = ("asian", "Asian")
        black = ("black", "Black or African American")
        caucasian = ("caucasian", "Caucasian / White")
        islander = ("islander", "Native Hawaiian or Other Pacific Islander")
        middle_eastern = ("middle_eastern", "Middle Eastern or North African")
        not_listed = ("not_listed", "An identity not listed (write-in)")
        latinx = ("latinx/a/o", "Latinx/a/o or Hispanic")
        native = ("native", "Native American / First Nations")
        no_answer = ("no_answer", "Prefer not to answer")

    class ABILITY(EnumClass):
        sensory = ("sensory", "A sensory impairment (vision or hearing)")
        learning = ("learning", "A learning disability (eg. ADHD, dyslexia)")
        medical = (
            "medical",
            "A long-term medical illness (eg. epilepsy, cystic fibrosis)",
        )
        mobility = ("mobility", "A mobility impairment")
        mental = ("mental", "A mental health disorder")
        temp = (
            "temp",
            "A temporary impairment due to illness or injury (eg. broken ankle, surgery)",
        )
        no_impairment = (
            "no_impairment",
            "I do not identify with a disability or impairment",
        )
        not_listed = ("not_listed", "A disability or impairment not listed (write-in)")
        no_answer = ("no_answer", "Prefer not to answer")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="demographic"
    )
    gender = MultiSelectField(
        _("How would you describe your gender identity? (Select all that apply)"),
        choices=[x.value for x in GENDER],
        default="no_answer",
        blank=True,
        null=True,
        max_length=500,
    )
    gender_write = models.CharField(
        _("Gender identity write-in"), max_length=30, blank=True, null=True
    )
    sexual = MultiSelectField(
        _("How would you describe your sexual identity? (Select all that apply)"),
        choices=[x.value for x in SEXUAL],
        default="no_answer",
        blank=True,
        null=True,
        max_length=500,
    )
    sexual_write = models.CharField(
        _("Sexual identity write-in"), max_length=30, blank=True, null=True
    )
    racial = MultiSelectField(
        _(
            "With which racial and ethnic group(s) do you identify? (Select all that apply)"
        ),
        choices=[x.value for x in RACIAL],
        default="no_answer",
        blank=True,
        null=True,
        max_length=500,
    )
    racial_write = models.CharField(
        _("Racial and ethnic identity write-in"), max_length=30, blank=True, null=True
    )
    specific_ethnicity = models.CharField(
        _(
            "Please print your specific ethnicities. "
            "Examples of ethnicities include (for example): "
            "German, Korean, Midwesterner (American), Mexican American, "
            "Navajo Nation, Samoan, Puerto Rican, Southerner (American), "
            "Chinese, etc. Note, you may report more that one group."
        ),
        max_length=300,
        blank=True,
        null=True,
    )
    ability = MultiSelectField(
        _(
            "How do you describe your disability / ability status? "
            "We are interested in this identification "
            "regardless of whether you typically request accommodations "
            "for this disability."
        ),
        choices=[x.value for x in ABILITY],
        default="no_answer",
        blank=True,
        null=True,
        max_length=500,
    )
    ability_write = models.CharField(
        _("Disability or impairment write-in"), max_length=30, blank=True, null=True
    )
    first_gen = models.BooleanField(
        _("Are you a first-generation college student?"),
        choices=BOOL_CHOICES,
        default=None,
        blank=True,
        null=True,
    )
    english = models.BooleanField(
        _("Is English your first language?"),
        choices=BOOL_CHOICES,
        default=None,
        blank=True,
        null=True,
    )


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
    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="service_hours_created",
    )
    modified_by = UserForeignKey(
        auto_user_add=True,
        auto_user=True,
        verbose_name="The user that created this object",
        related_name="service_hours_modified",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="service_hours"
    )
    service_hours = models.FloatField(default=0)


class UserSemesterGPA(YearTermModel):
    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="gpa_created",
    )
    modified_by = UserForeignKey(
        auto_user_add=True,
        auto_user=True,
        verbose_name="The user that created this object",
        related_name="gpa_modified",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="gpas"
    )
    gpa = models.FloatField()


class UserStatusChange(StartEndModel, TimeStampedModel, EmailSignalMixin):
    class STATUS(EnumClass):
        active = ("active", "Active")
        activeCC = ("activeCC", "Active")
        activepend = ("activepend", "Active Pending")
        advisor = ("advisor", "Advisor")
        alumni = ("alumni", "Alumni")
        alumniCC = ("alumniCC", "Alumni")
        alumnipend = ("alumnipend", "Alumni Pending")
        away = ("away", "Away")
        deceased = ("deceased", "Deceased")
        depledge = ("depledge", "Depledge")
        expelled = ("expelled", "Expelled")
        friend = ("friend", "Friend")
        nonmember = ("nonmember", "Nonmember")
        pendexpul = ("pendexpul", "Pending Expulsion")
        probation = ("probation", "Probation")
        pnm = ("pnm", "Prospective")
        resigned = ("resigned", "Resigned")
        resignedCC = ("resignedCC", "Resigned")
        suspended = ("suspended", "Suspended")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="status"
    )
    status = models.CharField(max_length=10, choices=[x.value for x in STATUS])
    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="status_change_created",
    )
    modified_by = UserForeignKey(
        auto_user_add=True,
        auto_user=True,
        verbose_name="The user that created this object",
        related_name="status_change_modified",
    )

    def __str__(self):
        return self.status

    def save(self, *args, **kwargs):
        if hasattr(self.start, "date"):
            self.start = self.start.date()
        if hasattr(self.end, "date"):
            self.end = self.end.date()
        if self.start <= TODAY < self.end:
            self.user.current_status = self.status
            self.user.save(update_fields=["current_status"])
        super().save(*args, **kwargs)


class UserRoleChange(StartEndModel, TimeStampedModel, EmailSignalMixin):
    ROLES = ALL_ROLES_CHOICES
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="roles"
    )
    role = models.CharField(max_length=50, choices=ROLES)
    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="role_change_created",
    )
    modified_by = UserForeignKey(
        auto_user_add=True,
        auto_user=True,
        verbose_name="The user that created this object",
        related_name="role_change_modified",
    )

    def __str__(self):
        return self.role

    def save(self, *args, **kwargs):
        off_group, _ = Group.objects.get_or_create(name="officer")
        nat_group, _ = Group.objects.get_or_create(name="natoff")
        super().save(*args, **kwargs)
        if hasattr(self.start, "date"):
            self.start = self.start.date()
        if hasattr(self.end, "date"):
            self.end = self.end.date()
        if self.start <= TOMORROW < self.end:
            current_roles = self.user.current_roles if self.user.current_roles else []
            if self.role not in current_roles:
                current_roles.append(self.role)
                self.user.current_roles = current_roles
                self.user.save(update_fields=["current_roles"])
        elif self.end < TODAY:
            current_roles = self.user.current_roles if self.user.current_roles else []
            if self.role in current_roles:
                self.user.current_roles.remove(self.role)
                self.user.save(update_fields=["current_roles"])
        self.clean_group_role()
        # Need to check current role, b/c user could have multiple
        current_officer = self.user.is_officer
        if current_officer:
            self.user.officer = True
            self.user.save(update_fields=["officer"])
            if self.user not in off_group.user_set.all():
                try:
                    off_group.user_set.add(self.user)
                except IntegrityError as e:
                    if "unique constraint" in str(e):
                        pass
            if self.user.is_national_officer():
                try:
                    nat_group.user_set.add(self.user)
                except IntegrityError as e:
                    if "unique constraint" in str(e):
                        pass
        else:
            self.user.officer = False
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
            # start__lte=TODAY_END,
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
    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="org_created",
    )
    modified_by = UserForeignKey(
        auto_user_add=True,
        auto_user=True,
        verbose_name="The user that created this object",
        related_name="org_modified",
    )
    org_name = models.CharField(max_length=50)
    type = models.CharField(max_length=3, choices=TYPES)
    officer = models.BooleanField(default=False)


class MemberUpdate(Process, EmailSignalMixin):
    # This will store all the information to update a member.
    class OUTCOME(EnumClass):
        matched = ("matched", "A member was found to update information")
        created = ("created", "A member was created to update information")
        denied = ("denied", "No member was found or created, update denied")

    # A member may not exist
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="updates",
        blank=True,
        null=True,
    )
    outcome = models.CharField(
        max_length=10,
        choices=[x.value for x in OUTCOME],
        default="matched",
        blank=True,
        null=True,
    )
    approved = models.BooleanField(default=True)
    chapter = models.ForeignKey(
        Chapter,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="member_updates",
    )
    badge_number = models.PositiveIntegerField(blank=True, null=True)
    title = models.CharField(blank=True, null=True, max_length=500)
    first_name = models.CharField(blank=True, null=True, max_length=500)
    middle_name = models.CharField(blank=True, null=True, max_length=500)
    last_name = models.CharField(blank=True, null=True, max_length=500)
    maiden_name = models.CharField(blank=True, null=True, max_length=500)
    preferred_pronouns = models.CharField(blank=True, null=True, max_length=500)
    preferred_name = models.CharField(blank=True, null=True, max_length=500)
    nickname = models.CharField(blank=True, null=True, max_length=500)
    suffix = models.CharField(blank=True, null=True, max_length=500)
    email = models.CharField(blank=True, null=True, max_length=500)
    email_school = models.CharField(blank=True, null=True, max_length=500)
    address = AddressField(
        on_delete=models.SET_NULL, blank=True, null=True, related_name="update"
    )
    birth_date = models.DateField(blank=True, null=True)
    phone_number = models.CharField(blank=True, null=True, max_length=500)
    graduation_year = models.PositiveIntegerField(blank=True, null=True)
    degree = models.CharField(blank=True, null=True, max_length=500)
    major = models.ForeignKey(
        ChapterCurricula,
        on_delete=models.SET_NULL,
        related_name="member_updates",
        blank=True,
        null=True,
    )
    major_other = models.CharField(blank=True, null=True, max_length=500)
    employer = models.CharField(blank=True, null=True, max_length=500)
    employer_position = models.CharField(blank=True, null=True, max_length=500)
    employer_address = AddressField(
        on_delete=models.SET_NULL, blank=True, null=True, related_name="update_employer"
    )
