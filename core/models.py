import datetime
from datetime import timedelta, time
from enum import Enum
from django.db import models
TODAY = datetime.datetime.now().date()
TOMORROW = TODAY + timedelta(1)
TODAY_START = datetime.datetime.combine(TODAY, time())
TODAY_END = datetime.datetime.combine(TOMORROW, time())

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
NATIONAL_OFFICER = {
    'regional director',
    'national director',
    'national officer'
}

COMMITTEE_CHAIR = {
    "alumni adviser",
    "board member",
    "committee chair",
    "employer/ee",
    "fundraising chair",
    "house corporation president",
    "other appointee",
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


ALL_OFFICERS = set.union(CHAPTER_OFFICER, COMMITTEE_CHAIR, NATIONAL_OFFICER)


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
    start = models.DateTimeField()
    end = models.DateTimeField()

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
