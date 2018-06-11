import datetime
from enum import Enum
from django.db import models


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
