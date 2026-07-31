from django.db import models
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from django_ckeditor_5.fields import CKEditor5Field

from core.models import TimeStampedModel

# Values (case-insensitive) that DISABLE a feature flag. A feature is enabled by
# default; set a flag Config's value to one of these to turn it off. Toggling is
# read live from the DB, so it takes effect on the next request (no redeploy).
FEATURE_FLAG_OFF_VALUES = frozenset({"0", "false", "no", "off", "disabled", "hide", "hidden"})


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

    @classmethod
    def feature_enabled(cls, key, default=True):
        """Return whether the feature-flag Config ``key`` is enabled.

        Features are enabled by default (a missing Config row means enabled).
        To disable a feature, add/edit its Config row with a value in
        ``FEATURE_FLAG_OFF_VALUES`` (e.g. ``off``). Because the value is read
        live from the database, toggling takes effect on the next request
        without redeploying or restarting the app.
        """
        raw = cls.get_value(key, clean=True).strip().lower()
        if raw == "":
            return default
        return raw not in FEATURE_FLAG_OFF_VALUES
