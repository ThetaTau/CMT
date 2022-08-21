from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from ckeditor_uploader.fields import RichTextUploadingField
from core.models import TimeStampedModel


class Announcement(TimeStampedModel):
    content = RichTextUploadingField()
    priority = models.IntegerField(
        verbose_name="Priority order, 1 highest",
        help_text="The order you want announcements to appear in, "
        "1 will be on top. Sorted by priority and then reverse published start date",
        default=10,
        choices=list(zip(range(1, 11), range(1, 11))),
        unique=False,
    )
    publish_start = models.DateTimeField(default=timezone.now)
    publish_end = models.DateTimeField(default=timezone.now)
    slug = models.SlugField(_("Slug"), max_length=255, unique=True, blank=True)
    title = models.CharField(_("Title"), max_length=255)

    class Meta:
        ordering = ["priority", "-publish_start"]
        verbose_name = "Announcement"

    def __unicode__(self):
        return "Announcement: %s" % self.title

    def save(self, *args, **kwargs):
        if not self.id:
            self.slug = slug = slugify(self.title)
            counter = 1
            while self.__class__.objects.filter(slug=self.slug).exists():
                self.slug = "{0}-{1}".format(slug, counter)
            counter += 1
        return super().save(*args, **kwargs)
