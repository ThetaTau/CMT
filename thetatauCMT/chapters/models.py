import warnings
from enum import Enum
from datetime import timedelta
from django.db import models
from django.db.models.functions import Concat
from django.db.utils import ProgrammingError
from address.models import AddressField
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify
from core.models import (
    TODAY_END,
    annotate_role_status,
    CHAPTER_OFFICER,
    semester_encompass_start_end_date,
    BIENNIUM_START,
    BIENNIUM_START_DATE,
    BIENNIUM_DATES,
    ADVISOR_ROLES,
)
from regions.models import Region


GREEK_ABR = {
    "a": "alpha",
    "albany": "ua colony",
    "ua": "ua colony",
    "b": "beta",
    "csf": "csf colony",
    "cslb": "cslb colony",
    "d": "delta",
    "dg": "delta gamma",
    "dxl": "drexel colony",
    "e": "epsilon",
    "eb": "epsilon beta",
    "ed": "epsilon delta",
    "eg": "epsilon gamma",
    "fit": "fit colony",
    "gb": "gamma beta",
    "h": "eta",
    "hd": "eta delta",
    "he": "eta epsilon",
    "hg": "eta gamma",
    "id": "iota delta",
    "ie": "iota epsilon",
    "ig": "iota gamma",
    "jmu": "jmu colony",
    "k": "kappa",
    "kb": "kappa beta",
    "kd": "kappa delta",
    "ke": "kappa epsilon",
    "kg": "kappa gamma",
    "lb": "lambda beta",
    "ld": "lambda delta",
    "le": "lambda epsilon",
    "lg": "lambda gamma",
    "m": "mu",
    "md": "mu delta",
    "me": "mu epsilon",
    "mg": "mu gamma",
    "nau": "nau colony",
    "nd": "nu delta",
    "ne": "nu epsilon",
    "ng": "nu gamma",
    "njit": "njit colony",
    "o": "omicron",
    "ob": "omicron beta",
    "od": "omicron delta",
    "og": "omicron gamma",
    "omb": "omega beta",
    "omg": "omega",
    "omga": "omega gamma",
    "omgd": "omega delta",
    "p": "rho",
    "pb": "rho beta",
    "pd": "rho delta",
    "pg": "rho gamma",
    "phd": "phi delta",
    "phg": "phi gamma",
    "phi": "phi",
    "pi": "pi",
    "pid": "pi delta",
    "pig": "pi gamma",
    "psb": "psi beta",
    "psd": "psi delta",
    "psg": "psi gamma",
    "row": "row colony",
    "s": "sigma",
    "scu": "scu colony",
    "sd": "sigma delta",
    "sg": "sigma gamma",
    "t": "tau",
    "tb": "tau beta",
    "td": "tau delta",
    "test": "test",
    "tg": "tau gamma",
    "thd": "theta delta",
    "the": "theta epsilon",
    "thg": "theta gamma",
    "tu": "tu colony",
    "u": "upsilon",
    "ub": "upsilon beta",
    "ucsb": "ucsb colony",
    "ud": "upsilon delta",
    "ug": "upsilon gamma",
    "unh": "unh colony",
    "uw": "uw colony",
    "vic": "victoria colony",
    "x": "chi",
    "xb": "chi beta",
    "xd": "chi delta",
    "xg": "chi gamma",
    "xi": "xi",
    "xib": "xi beta",
    "xid": "xi delta",
    "xig": "xi gamma",
    "z": "zeta",
    "zd": "zeta delta",
    "ze": "zeta epsilon",
    "zg": "zeta gamma",
}


class Chapter(models.Model):
    class Meta:
        ordering = [
            "name",
        ]

    TYPES = [
        ("semester", "Semester"),
        ("quarter", "Quarter"),
    ]

    class RECOGNITION(Enum):
        fraternity = ("fraternity", "Recognized as a Fraternity")
        org = ("org", "Recognized as a Student Organization NOT a Fraternity")
        other = ("other", "Recognized but not as a Fraternity or Student Organization")
        not_rec = ("not_rec", "Not Recognized by University")

        @classmethod
        def get_value(cls, member):
            if member == "not":
                member = "not_rec"
            return cls[member.lower()].value[1]

    name = models.CharField(max_length=50)
    modified = models.DateTimeField(auto_now=True)
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, related_name="chapters"
    )
    slug = models.SlugField(max_length=50, null=True, default=None, unique=True)
    email = models.EmailField(_("email address"), blank=True)
    website = models.URLField(
        blank=True,
        help_text="You must include the full URL including https:// or http://",
    )
    facebook = models.URLField(
        blank=True,
        help_text="You must include the full URL including https:// or http://",
    )
    address = AddressField(
        verbose_name=_("Mailing Address"),
        help_text="We periodically need to mail things (shingles, badges, etc) to your chapter.",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    balance = models.DecimalField(
        default=0, decimal_places=2, max_digits=7, help_text="Balance chapter owes."
    )
    balance_date = models.DateField(auto_now_add=True)
    tax = models.PositiveIntegerField(
        blank=True,
        null=True,
        unique=True,
        help_text="Tax number, if chapter participates in group exemption.",
    )
    greek = models.CharField(
        max_length=10, blank=True, help_text="Greek letter abbreviation"
    )
    active = models.BooleanField(default=True)
    colony = models.BooleanField(default=False)
    school = models.CharField(max_length=50, blank=True, unique=True)
    latitude = models.DecimalField(
        max_digits=22, decimal_places=16, blank=True, null=True
    )
    longitude = models.DecimalField(
        max_digits=22, decimal_places=16, blank=True, null=True
    )
    school_type = models.CharField(default="semester", max_length=10, choices=TYPES)
    council = models.CharField(
        verbose_name=_("Name of Council"),
        help_text="The name of the council of which your Chapter is a member, "
        + "for example the IFC or PFC.  Please write 'none' if you "
        + "are not recognized as a Fraternity or not a member of a council.",
        default="none",
        max_length=55,
    )
    recognition = models.CharField(
        verbose_name=_("University Recognition"),
        help_text="Please indicate if your chapter is recognized by your host college or university.",
        default="not_rec",
        max_length=10,
        choices=[x.value for x in RECOGNITION],
    )

    def __str__(self):
        return f"{self.name}"  # in {self.region} Region at {self.school}

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def account(self):
        suffix = "Ch"
        if self.colony:
            suffix = "Co"
        return f"{self.greek}0{suffix}"

    @property
    def full_name(self):
        suffix = "Chapter"
        if self.colony:
            suffix = "Colony"
        return f"{self.name} {suffix}"

    def get_actives_for_date(self, date):
        # Do not annotate, need the queryset not a list
        return self.members.filter(
            status__status__in=["active", "activepend", "alumnipend"],
            status__start__lte=date,
            status__end__gte=date,
        )

    def events_by_semester_biennium(self):
        semester_events = {}
        for names, dates in BIENNIUM_DATES.items():
            events = self.events.filter(
                date__lte=dates["end"], date__gte=dates["start"]
            )
            semester_events[names] = events

    def events_last_month(self):
        return self.events.filter(
            date__lte=TODAY_END, date__gte=TODAY_END - timedelta(30)
        )

    def events_semester(self):
        semester_start, semester_end = semester_encompass_start_end_date()
        return self.events.filter(date__lte=semester_end, date__gte=semester_start)

    def current_members(self):
        return self.actives() | self.pledges()

    @property
    def advisors_external(self):
        # Do not annotate, need the queryset not a list
        all_advisors = self.members.filter(
            status__status__in=["advisor",],
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END,
        )
        return all_advisors

    @property
    def advisors(self):
        # Do not annotate, need the queryset not a list
        all_advisors = self.members.filter(
            status__status__in=["advisor",],
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END,
        ) | self.members.filter(
            roles__role__in=ADVISOR_ROLES,
            roles__start__lte=TODAY_END,
            roles__end__gte=TODAY_END,
        )
        all_advisors = all_advisors.annotate(
            role=models.Case(
                models.When(
                    models.Q(roles__role__in=ADVISOR_ROLES),
                    Concat(models.Value("Alumni "), "roles__role"),
                ),
                default=models.Value("Faculty Advisor"),
                output_field=models.CharField(),
            )
        )
        return all_advisors

    def active_actives(self):
        # Do not annotate, need the queryset not a list
        """
        Must be only active to change status.
        eg. in prealumn form can not submit change
        for someone already grad (pendalum)
        :return:
        """
        return self.members.filter(
            status__status__in=["active", "activepend"],
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END,
        )

    def actives(self):
        # Do not annotate, need the queryset not a list
        return self.members.filter(
            status__status__in=["active", "activepend", "alumnipend"],
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END,
        )

    def pledges(self):
        # Do not annotate, need the queryset not a list
        return self.members.filter(
            status__status="pnm",
            status__start__lte=TODAY_END,
            status__end__gte=TODAY_END,
        )

    def depledges(self):
        return self.members.exclude(depledge__isnull=True,)

    def gpas(self):
        return self.current_members().filter(gpas__year__gte=BIENNIUM_START)

    def orgs(self):
        return self.current_members().filter(orgs__end__gte=BIENNIUM_START_DATE)

    def service_hours(self):
        return self.current_members().filter(service_hours__year__gte=BIENNIUM_START)

    def get_current_officers(self, combine=True):
        officers = self.members.filter(
            roles__start__lte=TODAY_END, roles__end__gte=TODAY_END
        )
        previous = False
        date = TODAY_END
        if officers.count() < 2:
            # If there are not enough previous officers
            # get officers from last 8 months
            previous_officers = self.members.filter(
                roles__end__gte=TODAY_END - timedelta(30 * 8)
            )
            officers = previous_officers | officers
            previous = True
            date = TODAY_END - timedelta(30 * 8)
        return annotate_role_status(officers, combine=combine, date=date), previous

    def get_current_officers_council(self, combine=True):
        officers = self.members.filter(
            roles__role__in=CHAPTER_OFFICER,
            roles__start__lte=TODAY_END,
            roles__end__gte=TODAY_END,
        )
        previous = False
        date = TODAY_END
        if officers.count() < 2:
            # If there are not enough previous officers
            # get officers from last 8 months
            previous_officers = self.members.filter(
                roles__role__in=CHAPTER_OFFICER,
                roles__end__gte=TODAY_END - timedelta(30 * 8),
            )
            officers = previous_officers | officers
            previous = True
            date = TODAY_END - timedelta(30 * 8)
        return annotate_role_status(officers, combine=combine, date=date), previous

    def get_current_officers_council_specific(self):
        officers = self.get_current_officers_council(combine=False)[0]
        regent = officers.filter(role="regent").first()
        scribe = officers.filter(role="scribe").first()
        vice = officers.filter(role="vice regent").first()
        treasurer = officers.filter(role="treasurer").first()
        return [regent, scribe, vice, treasurer]

    def next_badge_number(self):
        # Jan 2019 highest badge number was Mu with 1754
        max_badge = self.members.filter(
            ~models.Q(status__status="pnm"), ~models.Q(badge_number__gte=7000)
        ).aggregate(models.Max("badge_number"))
        max_badge = max_badge["badge_number__max"]
        if max_badge is None:
            max_badge = 0
        max_badge += 1
        return max_badge

    @property
    def next_advisor_number(self):
        badge_numbers = list(
            self.members.filter(
                badge_number__gte=7000, badge_number__lte=7999
            ).values_list("badge_number", flat=True)
        )
        if not badge_numbers:
            badge_numbers.append(6999)
        badge_number = max(badge_numbers) + 1
        return badge_number

    @classmethod
    def schools(cls):
        try:
            return [
                (school["pk"], school["school"])
                for school in cls.objects.values("school", "pk").order_by("school")
            ]
        except ProgrammingError:  # pragma: no cover
            # Likely the database hasn't been setup yet?
            warnings.warn("Could not find school relation")
            return []

    @classmethod
    def get_school_chapter(cls, school_name):
        try:
            return cls.objects.get(school=school_name,)
        except cls.DoesNotExist:
            warnings.warn("Could not find school")
            return None


class ChapterCurricula(models.Model):
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="curricula"
    )
    major = models.CharField(max_length=100)

    def __str__(self):
        return self.major
