from django.db import models
from django.utils.text import slugify
from core.models import ALL_OFFICERS
from chapters.models import Chapter


class Task(models.Model):
    class Meta:
        ordering = ['name', ]
    TYPES = [
        ('sub', 'Submission'),
        ('form', 'Forms'),
        ('task', 'Task'),
        ('bal', 'Balance'),
    ]
    OWNERS = [(officer, officer) for officer in ALL_OFFICERS]
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
    resource = models.URLField(blank=True)
    description = models.CharField(max_length=1000)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class TaskDate(models.Model):
    class Meta:
        unique_together = ('task', 'date', 'school_type')
        ordering = ['-date', ]

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
