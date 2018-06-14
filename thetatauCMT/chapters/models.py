from django.db import models
from django.conf import settings
from address.models import AddressField
from django.utils.translation import ugettext_lazy as _


class Region(models.Model):
    name = models.CharField(max_length=50)
    email = models.EmailField(_('email address'), blank=True)
    website = models.URLField()
    facebook = models.URLField()
    directors = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='region')


class Chapter(models.Model):
    name = models.CharField(max_length=50)
    region = models.ForeignKey(Region, related_name='chapters')
    email = models.EmailField(_('email address'), blank=True)
    website = models.URLField()
    address = AddressField()
