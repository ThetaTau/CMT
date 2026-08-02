from django.core.exceptions import ValidationError
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_ckeditor_5.fields import CKEditor5Field

from core.models import TimeStampedModel
from thetatauCMT.guides.models import Audience, validate_audience, validate_roles


class Announcement(TimeStampedModel):
    """A notice on the home page and in the What's New feed.

    The targeting and acknowledgement fields were added by TWI-6 and every
    default reproduces the pre-TWI-6 behaviour exactly: an untouched row is
    still shown to every signed-in user, and is now dismissible.

    ``guides`` never imports this module -- the dependency runs one way only, so
    :attr:`feature` is declared as a string reference.
    """

    content = CKEditor5Field()
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
    audience = models.CharField(
        _("Audience"),
        max_length=20,
        choices=Audience.choices,
        default=Audience.MEMBER,
        help_text="Minimum audience needed to see this announcement. 'Member' is every signed-in user.",
    )
    roles = models.JSONField(
        _("Roles"),
        default=list,
        blank=True,
        help_text="Show only to holders of these duty roles, e.g. ['treasurer']. Empty shows it to everyone.",
    )
    dismissible = models.BooleanField(
        _("Dismissible"),
        default=True,
        help_text="Uncheck for a compliance notice that must stay pinned until it expires.",
    )
    feature = models.ForeignKey(
        "guides.Feature",
        on_delete=models.SET_NULL,
        related_name="announcements",
        null=True,
        blank=True,
        verbose_name=_("Feature"),
        help_text="The catalog entry this announcement is about, if any. Enables the 'Show me' link.",
    )

    class Meta:
        ordering = ["priority", "-publish_start"]
        verbose_name = "Announcement"

    def __unicode__(self):
        return "Announcement: %s" % self.title

    def clean(self):
        super().clean()
        errors = {}
        try:
            validate_audience(self.audience)
        except ValidationError as error:
            errors["audience"] = error
        try:
            validate_roles(self.roles)
        except ValidationError as error:
            errors["roles"] = error
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.id:
            self.slug = slug = slugify(self.title)
            counter = 1
            while self.__class__.objects.filter(slug=self.slug).exists():
                self.slug = "{0}-{1}".format(slug, counter)
            counter += 1
        return super().save(*args, **kwargs)
