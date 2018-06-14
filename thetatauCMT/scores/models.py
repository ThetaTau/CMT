from enum import Enum
from django.db import models
from core.models import YearTermModel
from chapters.models import Chapter


class ScoreType(models.Model):
    class SECTION(Enum):
        brotherhood = ('Bro', 'Brotherhood')
        operate = ('Ops', 'Operate')
        professional = ('Pro', 'Professional')
        service = ('Ser', 'Service')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[0]

    class TYPES(Enum):
        event = ('Evt', 'Event')
        submit = ('Sub', 'Submit')
        special = ('Spe', 'Special')

        @classmethod
        def get_value(cls, member):
            return cls[member].value[0]

    name = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    section = models.CharField(
        max_length=3,
        choices=[x.value for x in SECTION]
    )
    points = models.PositiveIntegerField(default=0,
                               help_text="Total number of points possible in year")
    formula = models.CharField(max_length=200,
                               help_text="Formula for calculating score")
    name_short = models.CharField(max_length=20)
    type = models.CharField(
        max_length=3,
        choices=[x.value for x in TYPES]
    )
    base_points = models.PositiveIntegerField(default=0)
    attendance_multiplier = models.PositiveIntegerField(default=0)
    member_add = models.PositiveIntegerField(default=0)
    special = models.CharField(max_length=200)


class ScoreChapter(YearTermModel):
    chapter = models.ForeignKey(Chapter, related_name="scores")
    type = models.ForeignKey(ScoreType, related_name="chapters")
    score = models.PositiveIntegerField(default=0)
