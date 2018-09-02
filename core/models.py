import datetime
from datetime import timedelta, time
from enum import Enum
from django.db import models
from django.utils import timezone
TODAY = datetime.datetime.now().date()
TOMORROW = TODAY + timedelta(1)
TODAY_START = datetime.datetime.combine(TODAY, time())
TODAY_END = datetime.datetime.combine(TOMORROW, time())


def forever():
    return timezone.now() + timezone.timedelta(days=1000000)


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

CHAPTER_OFFICER = {
    "corresponding secretary",
    "president",
    "regent",
    "scribe",
    "secretary",
    "treasurer",
    "vice president",
    "vice regent",
}

COL_OFFICER_ALIGN = {
    "president": "regent",
    "secretary": "scribe",
    "vice president": "vice regent",
}

NATIONAL_OFFICER = {
    'regional director',
    'national director',
    'national officer'
}

COMMITTEE_CHAIR = {
    'academic chair',
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
    "rush chair",
    "scholarship chair",
    "service chair",
    "social/brotherhood chair",
    "website/social media chair",
}


ALL_OFFICERS = sorted(set.union(CHAPTER_OFFICER, COMMITTEE_CHAIR, NATIONAL_OFFICER))


ALL_OFFICERS_CHOICES = [(officer, officer.title()) for officer in ALL_OFFICERS]


class TimeStampedModel(models.Model):
    """
    An abstract base class model that provides self-
    updating ``created`` and ``modified`` fields.
    """
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StartEndModel(models.Model):
    """
    An abstract base class model that provides
    start and end dates.
    """
    start = models.DateField()
    end = models.DateField()

    class Meta:
        abstract = True


class YearTermModel(models.Model):
    """
    An abstract base class model that provides
    start and end dates.
    """
    class TERMS(Enum):
        fall = ('fa', 'Fall')
        spring = ('sp', 'Spring')
        winter = ('wi', 'Winter')
        summer = ('su', 'Summer')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[0]

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
        self.term = SEMESTER[datetime.datetime.now().month]
        super().save(*args, **kwargs)


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


def annotate_role_status(queryset, combine=True):
    qs = queryset.annotate(
        role=models.Case(
            models.When(
                models.Q(roles__start__lte=TODAY_END) &
                models.Q(roles__end__gte=TODAY_END), models.F("roles__role")
                ),
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
