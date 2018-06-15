from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.utils.text import slugify


class Region(models.Model):
    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50, null=True, default=None, unique=True)
    email = models.EmailField(_('email address'), blank=True)
    website = models.URLField()
    facebook = models.URLField()
    directors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='region')

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)
