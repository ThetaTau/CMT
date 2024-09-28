from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django_userforeignkey.models.fields import UserForeignKey
from email_signals.models import EmailSignalMixin
import os
from core.models import (
    TimeStampedModel,
    semester_encompass_start_end_date,
    BIENNIUM_START_DATE,
    BIENNIUM_END_DATE,
)
from scores.models import ScoreType
from chapters.models import Chapter


def get_event_upload_event(instance, filename):
    return os.path.join(
        "event-pictures", instance.type.slug, f"{instance.chapter.slug}_{filename}"
    )


class Event(TimeStampedModel, EmailSignalMixin):
    class Meta:
        unique_together = ("name", "date", "chapter")

    created_by = UserForeignKey(
        auto_user_add=True,
        verbose_name="The user that created this object",
        related_name="events_created",
    )
    modified_by = UserForeignKey(
        auto_user_add=True,
        auto_user=True,
        verbose_name="The user that created this object",
        related_name="events_modified",
    )
    name = models.CharField("Event Name", max_length=50)
    date = models.DateField("Event Date", default=timezone.now)
    slug = models.SlugField(unique=False)
    type = models.ForeignKey(ScoreType, on_delete=models.PROTECT, related_name="events")
    chapter = models.ForeignKey(
        Chapter, on_delete=models.CASCADE, related_name="events"
    )
    score = models.FloatField(default=0)
    description = models.CharField(max_length=200)
    # users = models.ManyToManyField(settings.AUTH_USER_MODEL,
    #                                related_name="events")
    members = models.PositiveIntegerField(default=0)
    alumni = models.PositiveIntegerField(default=0)
    pledges = models.PositiveIntegerField(default=0, verbose_name="PNMs")
    # Number of non members
    guests = models.PositiveIntegerField(default=0)
    duration = models.PositiveIntegerField(default=0)
    stem = models.BooleanField(
        default=False,
        help_text="Does the event relate to Science Technology Engineering or Math (STEM)?",
    )
    host = models.BooleanField(
        default=False, help_text="Did this event host another chapter?"
    )
    miles = models.PositiveIntegerField(
        default=0, help_text="Miles traveled to an event hosted by another chapter."
    )
    raised = models.DecimalField(
        default=0.00,
        decimal_places=2,
        max_digits=10,
        help_text="How many philanthropy funds " "were raised at this event?",
    )
    virtual = models.BooleanField(default=False, help_text="Was your event virtual?")

    def __str__(self):
        return f"{self.name} on {self.date}"

    def get_absolute_url(self):
        return (
            "events:detail",
            (),
            {
                "year": self.date.year,
                "month": self.date.strftime("%m"),
                "day": self.date.strftime("%d"),
                "slug": self.slug,
            },
        )

    def save(self, calculate_score=True, **kwargs):
        self.slug = slugify(self.name)
        if calculate_score:
            cal_score = self.type.calculate_score(self)
            self.score = cal_score
            super().save(**kwargs)
            self.type.update_chapter_score(self.chapter, self.date)
        else:
            super().save(**kwargs)

    @classmethod
    def chapter_events(cls, chapter):
        result = cls.objects.filter(chapter=chapter)
        return result

    @classmethod
    def calculate_meeting_attendance(cls, chapter, date):
        meeting_type = ScoreType.objects.get(name="Attendance at meetings")
        semester_start, semester_end = semester_encompass_start_end_date(date)
        events = cls.objects.filter(
            chapter=chapter,
            type=meeting_type,
            date__lte=semester_end,
            date__gte=semester_start,
        )
        total_percent = 0
        for event in events:
            actives = event.chapter.get_actives_for_date(event.date).count()
            percent_attendance = 0
            if actives:
                percent_attendance = min(event.members / actives, 1)
            total_percent += percent_attendance
        event_count = events.count()
        if not event_count:
            event_count = 1
        avg_attendance = total_percent / event_count
        formula_out = meeting_type.special
        formula_out = formula_out.replace("MEETINGS", str(avg_attendance))
        score = eval(formula_out)
        event_score = round(score / event_count, 2)
        for event in events:
            event.score = event_score
            event.save(calculate_score=False)
        return event_score

    @classmethod
    def count_events_biennium(cls, date=None, chapters=None):
        if date is None:
            query = cls.objects.filter(
                date__gte=BIENNIUM_START_DATE, date__lte=BIENNIUM_END_DATE
            )
        else:
            semester_start, semester_end = semester_encompass_start_end_date(date)
            cls.objects.filter(date__gte=semester_start, date__lte=semester_end)
        if chapters is None:
            chapters = Chapter.objects.exclude(active=False)
        events = (
            query.filter(chapter__in=chapters)
            .values("chapter", "type__section")
            .annotate(
                section_count=models.Count("name"),
                region=models.F("chapter__region__name"),
                chapter_name=models.F("chapter__name"),
            )
            .order_by("chapter_name")
        )
        grouped_events = {}
        for event in events:
            chapter = event["chapter"]
            event[f"{event.pop('type__section')}"] = event.pop("section_count")
            chapter_dict = grouped_events.get(
                chapter, {"Bro": 0, "Ops": 0, "Ser": 0, "Pro": 0}
            )
            chapter_dict.update(event)
            grouped_events[chapter] = chapter_dict
        for chapter, score in grouped_events.items():
            grouped_events[chapter]["total"] = round(
                score["Bro"] + score["Ops"] + score["Ser"] + score["Pro"], 2
            )
        return grouped_events.values()


def get_event_picture_upload_path(
    instance, filename
):  # instance refers to object road to data base
    return os.path.join(
        "event-pictures",
        f"{instance.event.chapter.slug}",  # name of chapter
        f"{filename}",  # name of file submitted
    )


class Picture(TimeStampedModel):
    description = models.TextField()
    image = models.ImageField(upload_to=get_event_picture_upload_path)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="pictures",
    )
