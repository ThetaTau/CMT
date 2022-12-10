from django.db import models
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
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

    @classmethod
    def get_value(cls, key, clean=True):
        value = cls.objects.filter(key=key).order_by("created").last()
        if value is not None:
            value = value.value
        else:
            value = ""
        if clean:
            # RichTextField value has HTML tags, when not needed strip
            value = strip_tags(value)
        else:
            value = mark_safe(value)
        return value
