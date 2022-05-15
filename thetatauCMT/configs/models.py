from django.db import models
from django.utils.html import strip_tags
from ckeditor.fields import RichTextField

from core.models import TimeStampedModel


class Config(TimeStampedModel):
    key = models.CharField(max_length=255)
    value = RichTextField()
    description = models.TextField()

    class Meta:
        ordering = [
            "-modified",
        ]

    def clean_value(self):
        # RichTextField value has HTML tags, when not needed strip
        return strip_tags(self.value)
