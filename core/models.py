import re
import time
import datetime
from datetime import timedelta, time
from enum import Enum
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
TODAY = datetime.datetime.now().date()
TOMORROW = TODAY + timedelta(1)
TODAY_START = datetime.datetime.combine(TODAY, time())
TODAY_END = datetime.datetime.combine(TOMORROW, time())


def forever():
    # Should be rooted so we can compare
    return datetime.datetime(2018, 1, 1) + timezone.timedelta(days=1000000)


SEMESTER = {
    0: 'sp',
    1: 'sp',
    2: 'sp',
    3: 'sp',
    4: 'sp',
    5: 'sp',
    6: 'sp',
    7: 'fa',
    8: 'fa',
    9: 'fa',
    10: 'fa',
    11: 'fa',
    12: 'fa',
}


current_year = datetime.datetime.now().year
if current_year % 2:
    # If the current year is odd, then first year of biennium is last year
    BIENNIUM_START = current_year - 1
else:
    # If the current year is even, then first year of biennium is
    # this year if current semester is fall otherwise two years ago
    current_month = datetime.datetime.now().month
    semester = SEMESTER[current_month]
    if semester == 'sp':
        BIENNIUM_START = current_year - 2
    else:
        BIENNIUM_START = current_year


BIENNIUM_START_DATE = datetime.date(BIENNIUM_START, 7, 1)
BIENNIUM_YEARS = [BIENNIUM_START, BIENNIUM_START + 1,
                  BIENNIUM_START + 1, BIENNIUM_START + 2]
BIENNIUM_DATES = {}
for i, year in enumerate(BIENNIUM_YEARS):
    year = BIENNIUM_YEARS[i]
    semester = 'Spring' if i % 2 else 'Fall'
    if semester == 'Spring':
        month_start = 1
        month_end = 6
        days = 30
    else:
        month_start = 7
        month_end = 12
        days = 31
    BIENNIUM_DATES[f"{semester} {year}"] = {
        'start': datetime.datetime(year, month_start, 1),
        'end': datetime.datetime(year, month_end, days),
    }


def current_term():
    return SEMESTER[datetime.datetime.now().month]


def current_year():
    return datetime.datetime.now().year


def current_year_term_slug():
    '''
    Fall_2019
    :return:
    '''
    term = {'fa': 'Fall', 'sp': 'Spring'}[current_term()]
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
    'grand regent',
    "grand scribe",
    "grand treasurer",
    "grand vice regent",
    'grand marshal',
    'grand inner guard',
    'grand outer guard',
    'council delegate',
}

NATIONAL_OFFICER = {
    'national operations manager',
    'regional director',
    'colony director',
    'expansion director',
    'professional development director',
    'service director',
    'alumni programs director',
    'national director',
    'national officer',
}

COMMITTEE_CHAIR = {
    'adviser',
    "board member",
    "committee chair",
    "employer/ee",
    'events chair',
    'faculty adviser',
    "fundraising chair",
    "house corporation president",
    "house corporation treasurer",
    "housing chair",
    "other appointee",
    'parent',
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
ALL_ROLES = sorted(set.union(set(ALL_OFFICERS), COMMITTEE_CHAIR))
CHAPTER_ROLES = sorted(set.union(CHAPTER_OFFICER, COMMITTEE_CHAIR))

ALL_OFFICERS_CHOICES = sorted([(officer, officer.title()) for officer in ALL_OFFICERS],
                              key=lambda x:x[0])
CHAPTER_OFFICER_CHOICES = sorted([(officer, officer.title()) for officer in CHAPTER_OFFICER],
                                 key=lambda x:x[0])
ALL_ROLES_CHOICES = sorted([(role, role.title()) for role in ALL_ROLES],
                           key=lambda x:x[0])
NAT_OFFICERS_CHOICES = sorted([(role, role.title()) for role in NAT_OFFICERS],
                              key=lambda x:x[0])
CHAPTER_ROLES_CHOICES = sorted([(role, role.title()) for role in CHAPTER_ROLES],
                               key=lambda x:x[0])


def semester_start_date():
    '''
    Determine the starting date of the current semester
    :return: date
    '''
    semester = SEMESTER[datetime.datetime.now().month]
    start_month = 1
    if semester == 'fa':
        start_month = 7
    return datetime.datetime(TODAY_END.year, start_month, 1)


def academic_encompass_start_end_date(given_date=None):
    '''
    Determine the start and end date of the academic year including given date
    :return: date
    '''
    if given_date is None:
        given_date = datetime.datetime.now()
    if isinstance(given_date, str) or isinstance(given_date, int):
        start_year = int(given_date)
        end_year = start_year + 1
    else:
        if SEMESTER[given_date.month] == 'sp':
            # If given spring semester then started last year
            start_year = given_date.year - 1
            end_year = given_date.year
        else:
            start_year = given_date.year
            end_year = given_date.year + 1
    return (datetime.datetime(start_year, 7, 1),
            datetime.datetime(end_year, 7, 1), )


class TimeStampedModel(models.Model):
    """
    An abstract base class model that provides self-
    updating ``created`` and ``modified`` fields.
    """
    created = models.DateTimeField(default=timezone.now)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


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
    year_re = re.compile('^\d{4}$')

    # If year does not match our regex:
    if not year_re.match(str(value)):
        raise ValidationError(u'%s is not a valid year.' % value)

    # Check not before this year:
    year = int(value)
    thisyear = time.localtime()[0]
    if year < thisyear:
        raise ValidationError(u'%s is a year in the past; please enter a current or future year.' % value)


class YearTermModel(models.Model):
    """
    An abstract base class model that provides
    start and end dates.
    """
    class TERMS(Enum):
        fa = ('fa', 'Fall')
        sp = ('sp', 'Spring')
        wi = ('wi', 'Winter')
        su = ('su', 'Summer')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[1]

    YEARS = []
    for r in range(2016, (datetime.datetime.now().year + 8)):
        YEARS.append((r, r))

    year = models.IntegerField(
        choices=YEARS,
        default=datetime.datetime.now().year)
    term = models.CharField(
        max_length=2,
        choices=[x.value for x in TERMS]
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.term is None or self.term == '':
            self.term = SEMESTER[datetime.datetime.now().month]
        super().save(*args, **kwargs)

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
        min_month, max_month = {'sp': (0, 6), 'fa': (7, 12)}[term]
        return datetime.date(date.year, min_month, 1), datetime.date(date.year, max_month, 1)


def combine_annotations(user_queryset):
    uniques = {user.pk: user for user in
               user_queryset.order_by('pk').distinct('pk')}
    duplicates = user_queryset.values('pk',
                                      ).annotate(models.Count('id')
                                                 ).order_by(
    ).filter(id__count__gt=1)
    # convert uniques to list and then update
    for duplicate in duplicates:
        pk = duplicate['pk']
        duplicate_objs = user_queryset.filter(pk=pk)
        for duplicate_obj in duplicate_objs:
            if duplicate_obj.role is not None:
                if uniques[pk].role is not None:
                    if duplicate_obj.role not in uniques[pk].role:
                        uniques[pk].role = ', '.join(
                            [duplicate_obj.role, uniques[pk].role])
                else:
                    uniques[pk].role = duplicate_obj.role
            if duplicate_obj.current_status is not None:
                if uniques[pk].current_status is not None:
                    if duplicate_obj.current_status not in uniques[pk].current_status:
                        uniques[pk].current_status = ', '.join(
                            [duplicate_obj.current_status, uniques[pk].current_status])
                else:
                    uniques[pk].current_status = duplicate_obj.current_status
    return list(uniques.values())


def annotate_role_status(queryset, combine=True, date=TODAY_END):
    qs = queryset.annotate(
        role=models.Case(
            models.When(
                models.Q(roles__start__lte=date) &
                models.Q(roles__end__gte=date), models.F("roles__role")
                ),
            )
        ).annotate(
            role_end=models.Case(
                models.When(
                    models.Q(roles__start__lte=date) &
                    models.Q(roles__end__gte=date), models.F("roles__end")
                )
            )
        ).annotate(
            current_status=models.Case(
                models.When(
                    models.Q(status__start__lte=TODAY_END) &
                    models.Q(status__end__gte=TODAY_END), models.F("status__status")
                )
            )
    )
    if combine:
        qs = combine_annotations(qs)
    return qs
