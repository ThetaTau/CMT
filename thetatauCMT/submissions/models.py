from django.db import models
from gdstorage.storage import GoogleDriveStorage
from core.models import TimeStampedModel
# Define Google Drive Storage
gd_storage = GoogleDriveStorage()


class Submission(TimeStampedModel):
    date = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='/media', storage=gd_storage)
    name = models.CharField(max_length=50)
    # type = # Related to score types
    score = models.PositiveIntegerField(default=0)
