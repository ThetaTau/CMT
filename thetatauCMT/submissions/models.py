import os
import datetime
import httplib2
import warnings
from django.db import models
from django.contrib.contenttypes.fields import GenericRelation
from gdstorage.storage import GoogleDriveStorage
from django.utils import timezone
from django.utils.text import slugify
from core.models import TimeStampedModel
from scores.models import ScoreType
from chapters.models import Chapter
from tasks.models import TaskChapter
try:
    # Define Google Drive Storage
    gd_storage = GoogleDriveStorage()
except httplib2.ServerNotFoundError as e:
    gd_storage = None
    warnings.warn(f'Unable to connect to Google drive!\n{e}')


def get_upload_path(instance, filename):
    return os.path.join(
        'media',
        datetime.datetime.now().date().strftime("%Y/%m/%d"), filename)


class Submission(TimeStampedModel):
    date = models.DateTimeField(default=timezone.now)
    file = models.FileField(upload_to=get_upload_path, storage=gd_storage)
    name = models.CharField(max_length=50)
    slug = models.SlugField(unique=False)
    type = models.ForeignKey(ScoreType, related_name="submissions",
                             on_delete=models.PROTECT)
    score = models.FloatField(default=0)
    chapter = models.ForeignKey(Chapter, related_name="submissions",
                                on_delete=models.CASCADE)
    task = GenericRelation(TaskChapter)

    def __str__(self):
        return f"{self.name}"  # from {self.chapter} on {self.date}"

    def save(self):
        self.slug = slugify(self.name)
        cal_score = self.type.calculate_score(self)
        self.score = cal_score
        super().save()

    def chapter_submissions(self, chapter):
        result = self.objects.filter(chapter=chapter)
        return result
