from django.db import models
from django.conf import settings
from core.models import TimeStampedModel
from scores.models import ScoreType
from chapters.models import Chapter


class Event(TimeStampedModel):
    name = models.CharField(max_length=50)
    date = models.DateTimeField(auto_now_add=True)
    type = models.ForeignKey(ScoreType)
    chapter = models.ForeignKey(Chapter)
    score = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=200)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL)
    # Number of non members
    guests = models.PositiveIntegerField(default=0)
    duration = models.PositiveIntegerField(default=0)
    stem = models.BooleanField()
    host = models.BooleanField()
    miles = models.PositiveIntegerField(default=0)
