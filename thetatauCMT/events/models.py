from django.db import models
from django.conf import settings
from core.models import TimeStampedModel
from scores.models import ScoreType
from chapters.models import Chapter


class Event(TimeStampedModel):
    class Meta:
        unique_together = ('name', 'date', 'chapter')

    name = models.CharField(max_length=50)
    date = models.DateTimeField(auto_now_add=True)
    type = models.ForeignKey(ScoreType, on_delete=models.PROTECT,
                             related_name="events")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                related_name="events")
    score = models.FloatField(default=0)
    description = models.CharField(max_length=200)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                   related_name="events")
    # Number of non members
    guests = models.PositiveIntegerField(default=0)
    duration = models.PositiveIntegerField(default=0)
    stem = models.BooleanField(
        default=False,
        help_text="Does the event relate to Science Technology Engineering or Math (STEM)?")
    host = models.BooleanField(
        default=False,
        help_text="Did this event host another chapter?")
    miles = models.PositiveIntegerField(
        default=0,
        help_text="Miles traveled to an event hosted by another chapter.")

    def __str__(self):
        return f"{self.name} at {self.chapter} on {self.date}"

    def chapter_events(self, chapter):
        result = self.objects.filter(chapter=chapter)
        return result

