import datetime
from datetime import timedelta, time
from enum import Enum
from django.db import models
TODAY = datetime.datetime.now().date()
TOMORROW = TODAY + timedelta(1)
TODAY_START = datetime.datetime.combine(TODAY, time())
TODAY_END = datetime.datetime.combine(TOMORROW, time())

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
    'adviser',
    "board member",
    "committee chair",
    "employer/ee",
    "fundraising chair",
    "house corporation president",
    "house corporation treasurer"
    "housing chair",
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
    'parent',
    'faculty adviser',
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

    def save(self, *args, **kwargs):
        self.term = SEMESTER[datetime.datetime.now().month]
        super().save(*args, **kwargs)
