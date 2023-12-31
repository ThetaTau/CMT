import re
import datetime
from datetime import timedelta, time
from enum import Enum
from django.db import IntegrityError, transaction
from django.contrib.postgres.aggregates import StringAgg, ArrayAgg
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils import timezone

TODAY = datetime.datetime.now().date()
TOMORROW = TODAY + timedelta(1)
TODAY_START = datetime.datetime.combine(TODAY, time())
TODAY_END = datetime.datetime.combine(TOMORROW, time())


def forever():
    # Should be rooted so we can compare
    return datetime.datetime(2018, 1, 1) + timezone.timedelta(days=1000000)


def no_future(value):
    today = datetime.date.today()
    if value > today:
        raise ValidationError("Date cannot be in the future.")


SEMESTER = {
    0: "sp",
    1: "sp",
    2: "sp",
    3: "sp",
    4: "sp",
    5: "sp",
    6: "sp",
    7: "fa",
    8: "fa",
    9: "fa",
    10: "fa",
    11: "fa",
    12: "fa",
}


def current_year():
    return datetime.datetime.now().year


def current_month():
    return datetime.datetime.now().month


current_year_value = current_year()

if (current_year_value % 2) == 0:
    # If the current year is even, then first year of biennium is last year
    BIENNIUM_START = current_year_value - 1
else:
    # If the current year is odd, then first year of biennium is
    # this year if current semester is fall otherwise two years ago
    semester = SEMESTER[current_month()]
    if semester == "sp":
        BIENNIUM_START = current_year_value - 2
    else:
        BIENNIUM_START = current_year_value


BIENNIUM_START_DATE = datetime.date(BIENNIUM_START, 7, 1)
BIENNIUM_END_DATE = datetime.date(BIENNIUM_START + 2, 7, 1)
BIENNIUM_YEARS = [
    BIENNIUM_START,
    BIENNIUM_START + 1,
    BIENNIUM_START + 1,
    BIENNIUM_START + 2,
]
BIENNIUM_DATES = {}
for i, year in enumerate(BIENNIUM_YEARS):
    year = BIENNIUM_YEARS[i]
    semester = "Spring" if i % 2 else "Fall"
    if semester == "Spring":
        month_start = 1
        month_end = 6
        days = 30
    else:
        month_start = 7
        month_end = 12
        days = 31
    BIENNIUM_DATES[f"{semester} {year}"] = {
        "start": datetime.datetime(year, month_start, 1),
        "end": datetime.datetime(year, month_end, days),
    }


def current_term():
    return SEMESTER[datetime.datetime.now().month]


def current_year():
    return datetime.datetime.now().year


def current_year_plus_10():
    return current_year() + 10


def current_year_term_slug():
    """
    Fall_2019
    :return:
    """
    term = {"fa": "Fall", "sp": "Spring"}[current_term()]
    return f"{term}_{current_year()}"


CHAPTER_OFFICER = {
    "corresponding secretary",
    "regent",
    "scribe",
    "treasurer",
    "vice regent",
}

COL_OFFICER_ALIGN = {
    "president": "regent",
    "secretary": "scribe",
    "vice president": "vice regent",
}

COUNCIL = {
    "grand regent",
    "grand scribe",
    "grand treasurer",
    "grand vice regent",
    "grand marshal",
    "grand inner guard",
    "grand outer guard",
    "council delegate",
}

NATIONAL_OFFICER = {
    "national operations manager",
    "regional director",
    "candidate chapter director",
    "expansion director",
    "professional development director",
    "service director",
    "alumni programs director",
    "national director",
    "national officer",
    "educational foundation board of director",
}


ADVISOR_ROLES = {
    "adviser",
    "faculty adviser",
    "house corporation president",
    "house corporation treasurer",
}


COMMITTEE_CHAIR = {
    "board member",
    "committee chair",
    "diversity, equity, and inclusion chair",
    "employer/ee",
    "events chair",
    "fundraising chair",
    "housing chair",
    "marshal",
    "other appointee",
    "parent",
    "pd chair",
    "pledge/new member educator",
    "project chair",
    "recruitment chair",
    "risk management chair",
    "rube goldberg chair",
    "recruitment chair",
    "scholarship chair",
    "service chair",
    "social/brotherhood chair",
    "website/social media chair",
}


NAT_OFFICERS = sorted(set.union(NATIONAL_OFFICER, COUNCIL))
ALL_OFFICERS = sorted(set.union(CHAPTER_OFFICER, set(NAT_OFFICERS)))
ALL_ROLES = sorted(set.union(set(ALL_OFFICERS), COMMITTEE_CHAIR, ADVISOR_ROLES))
CHAPTER_ROLES = sorted(set.union(CHAPTER_OFFICER, COMMITTEE_CHAIR, ADVISOR_ROLES))

ALL_OFFICERS_CHOICES = sorted(
    [(officer, officer.title()) for officer in ALL_OFFICERS], key=lambda x: x[0]
)
CHAPTER_OFFICER_CHOICES = sorted(
    [(officer, officer.title()) for officer in CHAPTER_OFFICER], key=lambda x: x[0]
)
ALL_ROLES_CHOICES = sorted(
    [(role, role.title()) for role in ALL_ROLES], key=lambda x: x[0]
)
NAT_OFFICERS_CHOICES = sorted(
    [(role, role.title()) for role in NAT_OFFICERS], key=lambda x: x[0]
)
CHAPTER_ROLES_CHOICES = sorted(
    [(role, role.title()) for role in CHAPTER_ROLES], key=lambda x: x[0]
)


def semester_encompass_start_end_date(given_date=None, term=None, year=None):
    """
    Determine the start and end date of the semester including given date
    :return: date
    """
    if given_date is None:
        if not year:
            year = current_year()
        if not term:
            term = current_term()
        month = {"fa": 10, "sp": 3}[term]
        given_date = datetime.datetime(year, month, 1)
    term = SEMESTER[given_date.month]
    start_month = 1
    end_month = 7
    year = given_date.year
    if term == "fa":
        # start in July and end in January 1
        start_month, end_month = end_month, start_month
        year += 1
    return (
        datetime.datetime(given_date.year, start_month, 1),
        datetime.datetime(year, end_month, 1),
    )


def academic_encompass_start_end_date(given_date=None):
    """
    Determine the start and end date of the academic year including given date
    :return: date
    """
    if given_date is None:
        given_date = datetime.datetime.now()
    if isinstance(given_date, str) or isinstance(given_date, int):
        start_year = int(given_date)
        end_year = start_year + 1
    else:
        if SEMESTER[given_date.month] == "sp":
            # If given spring semester then started last year
            start_year = given_date.year - 1
            end_year = given_date.year
        else:
            start_year = given_date.year
            end_year = given_date.year + 1
    return (
        datetime.datetime(start_year, 7, 1),
        datetime.datetime(end_year, 7, 1),
    )


class TimeStampedModel(models.Model):
    """
    An abstract base class model that provides self-
    updating ``created`` and ``modified`` fields.
    """

    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class EnumClass(Enum):
    @classmethod
    def get_value(cls, member):
        value = ""
        if hasattr(cls, member):
            value = cls[member].value[1]
        return value


class StartEndModel(models.Model):
    """
    An abstract base class model that provides
    start and end dates.
    """

    start = models.DateField("Start Date")
    end = models.DateField("End Date")

    class Meta:
        abstract = True


def validate_year(value):
    """
    Validator function for model.IntegerField()
    * Validates a valid four-digit year.
    * Must be a current or future year.
    In your model:
    year = models.IntegerField(_(u'Year'), help_text=_(u'Current or future year in YYYY format.'), validators=[
    validate_year], unique=True)
    """

    # Matches any 4-digit number:
    year_re = re.compile("^\d{4}$")  # noqa: W605

    # If year does not match our regex:
    if not year_re.match(str(value)):
        raise ValidationError("%s is not a valid year." % value)

    # Check not before this year:
    year = int(value)
    thisyear = datetime.datetime.now().year
    if year < thisyear:
        raise ValidationError(
            "%s is a year in the past; please enter a current or future year." % value
        )


class YearTermModel(models.Model):
    """
    An abstract base class model that provides
    start and end dates.
    """

    class TERMS(Enum):
        fa = ("fa", "Fall")
        sp = ("sp", "Spring")
        wi = ("wi", "Winter")
        su = ("su", "Summer")

        @classmethod
        def get_value(cls, member):
            return cls[member].value[1]

    year = models.IntegerField(
        default=current_year,
        validators=[
            MinValueValidator(2016),
            MaxValueValidator(current_year_plus_10),
        ],
    )
    term = models.CharField(max_length=2, choices=[x.value for x in TERMS])

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.term is None or self.term == "":
            self.term = SEMESTER[datetime.datetime.now().month]
        try:
            with transaction.atomic():
                super().save(*args, **kwargs)
        except IntegrityError as e:
            if "unique constraint" in str(e):
                pass
            else:
                raise e

    def get_date(self):
        month = {"fa": 8, "sp": 2}[self.term]
        return datetime.datetime(self.year, month, 1)

    @staticmethod
    def get_term(date):
        return SEMESTER[date.month]

    @classmethod
    def current_term(cls):
        return SEMESTER[datetime.datetime.now().month]

    @classmethod
    def current_year(cls):
        return datetime.datetime.now().year

    @staticmethod
    def date_range(date):
        """
        Date range for semester that encompasses date
        :param date: datetime date
        :return: start_date, end_date
        """
        month = date.month
        term = SEMESTER[month]
        _year = date.year
        if term == "fa":
            # start in July and end in January 1
            _year += 1
        min_month, max_month = {"sp": (1, 7), "fa": (7, 1)}[term]
        return (
            datetime.date(date.year, min_month, 1),
            datetime.date(_year, max_month, 1),
        )


def annotate_rmp_status(queryset, date=TODAY_END):
    from forms.models import RiskManagement

    start, end = semester_encompass_start_end_date(date)
    qs = queryset.annotate(
        rmp_complete=models.Exists(
            RiskManagement.objects.filter(
                user=models.OuterRef("pk"), date__gte=start, date__lte=end
            ),
        )
    )
    return qs


def annotate_role_status(queryset, date=TODAY_END):
    from forms.models import RiskManagement

    start, end = semester_encompass_start_end_date(date)
    qs = (
        queryset.annotate(
            roles_all=models.FilteredRelation(
                "roles",
                condition=models.Q(roles__start__lte=date)
                & models.Q(roles__end__gte=date),
            )
        )
        .annotate(old_roles=StringAgg("roles_all__role", ", "))
        .annotate(
            status_all=models.FilteredRelation(
                "status",
                condition=models.Q(status__start__lte=date)
                & models.Q(status__end__gte=date),
            )
        )
        .annotate(old_status=StringAgg("status_all__status", ", "))
        .annotate(
            rmp_complete=models.Exists(
                RiskManagement.objects.filter(
                    user=models.OuterRef("pk"), date__gte=start, date__lte=end
                ),
            )
        )
    )
    return qs
