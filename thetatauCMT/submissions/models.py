import os
import datetime
from django.db import models
from gdstorage.storage import GoogleDriveStorage
from core.models import TimeStampedModel
from scores.models import ScoreType
from chapters.models import Chapter
# Define Google Drive Storage
gd_storage = GoogleDriveStorage()


def get_upload_path(instance, filename):
    return os.path.join(
        '/media/submissions',
        datetime.datetime.now().date().strftime("%Y/%m/%d"), filename)


class Submission(TimeStampedModel):
    date = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to=get_upload_path, storage=gd_storage)
    name = models.CharField(max_length=50)
    type = models.ForeignKey(ScoreType, related_name="submissions")
    score = models.FloatField(default=0)
    chapter = models.ForeignKey(Chapter, related_name="submissions")
