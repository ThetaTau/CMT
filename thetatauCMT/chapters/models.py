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
    region = models.ForeignKey(Region, on_delete=models.PROTECT,
                               related_name='chapters')
    email = models.EmailField(_('email address'), blank=True)
    website = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    address = AddressField(on_delete=models.SET_NULL, blank=True, null=True, unique=True)
    balance = models.DecimalField(default=0, decimal_places=2,
                                  max_digits=7,
                                  help_text="Balance chapter owes.")
    tax = models.PositiveIntegerField(
        help_text="Tax number, if chapter participates in group exemption.")
    greek = models.CharField(max_length=2, blank=True,
                             help_text="Greek letter abbreviation")
    active = models.BooleanField(default=True)
    school = models.CharField(max_length=50, blank=True)
