from django.db import models
from django.db.models import Q
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.text import slugify
from core.models import ALL_OFFICERS
from chapters.models import Chapter
from scores.models import ScoreType


class Task(models.Model):
    class Meta:
        ordering = ['name', ]
    TYPES = [
        ('sub', 'Submission'),
        ('form', 'Forms'),
        ('task', 'Task'),
        ('bal', 'Balance'),
    ]
    OWNERS = [(officer, officer.title()) for officer in ALL_OFFICERS]
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    owner = models.CharField(
        max_length=50,
        choices=OWNERS
    )
    type = models.CharField(
        max_length=4,
        choices=TYPES
    )
    resource = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=1000)
    submission_type = models.ForeignKey(ScoreType, on_delete=models.CASCADE,
                                        related_name="task",
                                        blank=True, null=True)

    def __str__(self):
        return f"{self.name}"

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def all_dates_for_task_chapter(self, chapter):
        school_type = chapter.school_type
        dates = self.dates.filter(Q(school_type=school_type) |
                                  Q(school_type='all')).all()
        return dates

    def incomplete_dates_for_task_chapter(self, chapter):
        school_type = chapter.school_type
        dates = self.dates.filter(Q(school_type=school_type) |
                                  Q(school_type='all'),
                                  ~Q(chapters__chapter=chapter)).all()
        return dates


class TaskDate(models.Model):
    class Meta:
        unique_together = ('task', 'date', 'school_type')
        ordering = ['date', ]

    TYPES = [
        ('semester', 'Semester'),
        ('quarter', 'Quarter'),
        ('all', 'All'),
        ('na', 'N/A')
    ]
    task = models.ForeignKey(Task, on_delete=models.CASCADE,
                             related_name="dates")
    school_type = models.CharField(
        max_length=10,
        choices=TYPES
    )
    date = models.DateTimeField()

    def __str__(self):
        return f"{self.task.name} on {self.date}"

    def complete(self, chapter):
        tasks = self.chapters.filter(chapter=chapter).all()
        return tasks

    @classmethod
    def incomplete_dates_for_chapter(cls, chapter):
        school_type = chapter.school_type
        tasks = cls.objects.filter(Q(school_type=school_type) |
                                   Q(school_type='all'),
                                   ~Q(chapters__chapter=chapter)).all()
        return tasks

    @classmethod
    def dates_for_chapter(cls, chapter):
        school_type = chapter.school_type
        tasks = cls.objects.filter(Q(school_type=school_type) |
                                   Q(school_type='all')).all()
        return tasks


class TaskChapter(models.Model):
    class Meta:
        unique_together = ('task', 'date', 'chapter')
        """Dates increase as time advances, so 1293861600 (Jan. 1st 2011) is greater than 946706400 (Jan 1st. 2000).
        Thus, a descending ordering puts the most recent dates first."""
        ordering = ['chapter', '-date']

    task = models.ForeignKey(TaskDate, on_delete=models.CASCADE,
                             related_name="chapters")
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE,
                                related_name="tasks")
    date = models.DateTimeField()
    # This can only be used for a submission or form
    # Whatever results in the completion of the task
    submission_type = models.ForeignKey(ContentType, on_delete=models.CASCADE,
                                        blank=True, null=True)
    submission_id = models.PositiveIntegerField(blank=True, null=True)
    submission_object = GenericForeignKey('submission_type', 'submission_id')
