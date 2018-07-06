import os
import datetime
from django.db import models
from gdstorage.storage import GoogleDriveStorage
from django.utils import timezone
from django.utils.text import slugify
from core.models import TimeStampedModel
from scores.models import ScoreType
from chapters.models import Chapter
# Define Google Drive Storage
gd_storage = GoogleDriveStorage()


def get_upload_path(instance, filename):
    return os.path.join(
        'media/submissions',
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

    def __str__(self):
        return f"{self.name}"  # from {self.chapter} on {self.date}"

    def save(self):
        self.slug = slugify(self.name)
        super().save()
        print("Done")
    #     cal_score = self.type.calculate_score(self)
    #     self.score = cal_score
    #     super().save()

    def chapter_submissions(self, chapter):
        result = self.objects.filter(chapter=chapter)
        return result
