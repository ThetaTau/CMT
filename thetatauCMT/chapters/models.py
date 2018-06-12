from django.db import models
from address.models import AddressField
from django.utils.translation import ugettext_lazy as _


class Chapter(models.Model):
    name = models.CharField(max_length=50)
    region = models.CharField(max_length=50)
    email = models.EmailField(_('email address'), blank=True)
    website = models.URLField()
    address = AddressField()
