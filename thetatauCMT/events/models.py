from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from core.models import TimeStampedModel
from scores.models import ScoreType
from chapters.models import Chapter


class Event(TimeStampedModel):
    class Meta:
        unique_together = ('name', 'date', 'chapter')

    name = models.CharField(max_length=50)
    date = models.DateField("Event Date", default=timezone.now)
    slug = models.SlugField(unique=False)
    type = models.ForeignKey(ScoreType, on_delete=models.PROTECT,
                             related_name="events")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                related_name="events")
    score = models.FloatField(default=0)
    description = models.CharField(max_length=200)
    # users = models.ManyToManyField(settings.AUTH_USER_MODEL,
    #                                related_name="events")
    members = models.PositiveIntegerField(default=0)
    alumni = models.PositiveIntegerField(default=0)
    pledges = models.PositiveIntegerField(default=0)
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
        return f"{self.name} on {self.date}"

    @models.permalink
    def get_absolute_url(self):
        return (
            'events:detail', (), {
                'year': self.date.year,
                'month': self.date.strftime("%m"),
                'day': self.date.strftime("%d"),
                'slug': self.slug
                })

    def save(self):
        self.slug = slugify(self.name)
        cal_score = self.type.calculate_score(self)
        self.score = cal_score
        super().save()
        self.type.update_chapter_score(self.chapter, self.date)

    def chapter_events(self, chapter):
        result = self.objects.filter(chapter=chapter)
        return result

