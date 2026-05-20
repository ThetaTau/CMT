from django.db import models
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django_ckeditor_5.fields import CKEditor5Field

from core.models import TimeStampedModel


class Config(TimeStampedModel):
    key = models.CharField(max_length=255)
    value = CKEditor5Field()
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
            # CKEditor5Field value has HTML tags, when not needed strip
            value = strip_tags(value)
        else:
            value = mark_safe(value)
        return value
