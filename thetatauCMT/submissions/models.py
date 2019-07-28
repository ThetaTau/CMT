import os
import datetime
from django.db import models, transaction
from django.contrib.contenttypes.fields import GenericRelation
from django.utils import timezone
from django.utils.text import slugify
from core.models import TimeStampedModel, gd_storage
from scores.models import ScoreType
from chapters.models import Chapter
from tasks.models import TaskChapter


def get_upload_path(instance, filename):
    return os.path.join(
        'media',
        datetime.datetime.now().date().strftime("%Y/%m/%d"), filename)


class Submission(TimeStampedModel):
    date = models.DateField("Submission Date", default=timezone.now)
    file = models.FileField(upload_to=get_upload_path, storage=gd_storage)
    name = models.CharField("Submission Name", max_length=50)
    slug = models.SlugField(unique=False)
    type = models.ForeignKey(ScoreType, related_name="submissions",
                             on_delete=models.PROTECT)
    score = models.FloatField(default=0)
    chapter = models.ForeignKey(Chapter, related_name="submissions",
                                on_delete=models.CASCADE)
    task = GenericRelation(TaskChapter)

    def __str__(self):
        return f"{self.name}"  # from {self.chapter} on {self.date}"

    def save(self, extra_info=None):
        self.slug = slugify(self.name)
        cal_score = self.type.calculate_score(self, extra_info=extra_info)
        self.score = cal_score
        try:
            with transaction.atomic():
                super().save()
        except TimeoutError:
            pass  # Really want to remove all file uploads, ignore for now
        except BrokenPipeError:
            pass
        self.type.update_chapter_score(self.chapter, self.date)

    def chapter_submissions(self, chapter):
        result = self.objects.filter(chapter=chapter)
        return result
