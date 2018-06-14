from django.db import models
from gdstorage.storage import GoogleDriveStorage
from core.models import TimeStampedModel
from scores.models import ScoreType
from chapters.models import Chapter
# Define Google Drive Storage
gd_storage = GoogleDriveStorage()


class Submission(TimeStampedModel):
    date = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='/media', storage=gd_storage)
    name = models.CharField(max_length=50)
    type = models.ForeignKey(ScoreType, related_name="submissions")
    score = models.PositiveIntegerField(default=0)
    chapter = models.ForeignKey(Chapter, related_name="submissions")
