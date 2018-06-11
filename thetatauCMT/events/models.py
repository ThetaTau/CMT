from django.db import models
from core.models import TimeStampedModel
from users.models import User


class Event(TimeStampedModel):
    name = models.CharField(max_length=50)
    date = models.DateTimeField(auto_now_add=True)
    # type = # Related to event types
    score = models.PositiveIntegerField(default=0)
    description = models.CharField(max_length=200)
    # Number of non members
    guests = models.PositiveIntegerField(default=0)
    duration = models.PositiveIntegerField(default=0)
    stem = models.BooleanField()
    host = models.BooleanField()
    miles = models.PositiveIntegerField(default=0)


class EventMemberAttendance(models.Model):
    event = models.ForeignKey(Event)
    user = models.ForeignKey(User)
