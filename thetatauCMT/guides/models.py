"""Registry models for the feature catalog and role guides (TWI-2).

The catalog is content, not code: every entry is a row an administrator can edit
rather than a hard-coded template block. :class:`FeatureArea` groups the
application into browsable sections and :class:`Feature` describes a single thing
a user can do.

Three field conventions are shared across the app and repeated on the models:

``audience``
    One of ``public`` / ``member`` / ``officer`` / ``natoff``. A single value,
    not a list, because the audiences form a strict hierarchy in this codebase
    (``OfficerRequiredMixin`` admits officers *and* National Officers *and*
    superusers). It mirrors the mixin the real view uses, so the catalog never
    advertises a page that would bounce the viewer. ``public`` is reserved for
    the small "getting signed in" set.

``roles``
    Duty-role targeting only -- "this is a Treasurer thing" -- validated against
    :data:`core.models.ALL_ROLES`. Never used for access control.

``feature_flag``
    When set, the entry is hidden unless
    :meth:`thetatauCMT.configs.models.Config.feature_enabled` returns true.
    Known keys today are ``FEATURE_AWARDS``, ``FEATURE_JOBS`` and
    ``FEATURE_EVENTS_CALENDAR``.

``key`` is the stable identity the registry fixture addresses rows by. It is
unique and, in practice, immutable: renaming one orphans the fixture entry.
"""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from core.models import ALL_ROLES, ALL_ROLES_CHOICES, TimeStampedModel


class Audience(models.TextChoices):
    """Minimum privilege needed to see a catalog entry, lowest first."""

    PUBLIC = "public", _("Public")
    MEMBER = "member", _("Member")
    OFFICER = "officer", _("Officer")
    NATOFF = "natoff", _("National Officer")


def validate_audience(value):
    """Reject an audience outside :class:`Audience`.

    Django already enforces ``choices`` in ``full_clean()``; this exists so the
    models can raise the same error from ``clean()``, which is what the fixture
    loader calls.
    """
    if value and value not in Audience.values:
        raise ValidationError(
            _("Unknown audience %(value)s. Choose one of: %(valid)s."),
            params={"value": value, "valid": ", ".join(Audience.values)},
        )


def validate_roles(value):
    """Reject anything that is not a list of known duty roles."""
    if not value:
        return
    if not isinstance(value, list):
        raise ValidationError(_("Roles must be a list of role names."))
    unknown = sorted(set(value) - set(ALL_ROLES))
    if unknown:
        raise ValidationError(
            _("Unknown role(s): %(roles)s"),
            params={"roles": ", ".join(unknown)},
        )


class FeatureAreaQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class FeatureArea(TimeStampedModel):
    """A browsable section of the application, e.g. "Finances" or "Awards".

    Areas are the top level of the catalog.
    """

    key = models.SlugField(
        _("Key"),
        max_length=100,
        unique=True,
        help_text="Stable identifier used by the registry fixture, e.g. 'events-attendance'. Do not rename.",
    )
    name = models.CharField(_("Name"), max_length=100)
    description = models.TextField(
        _("Description"),
        help_text="Shown at the top of the catalog section.",
    )
    icon = models.CharField(
        _("Icon"),
        max_length=50,
        blank=True,
        help_text="Font Awesome 6 class, e.g. 'fa-solid fa-calendar-days'.",
    )
    order = models.PositiveSmallIntegerField(
        _("Order"),
        default=0,
        help_text="Display order in the catalog; lower sorts first.",
    )
    audience = models.CharField(
        _("Audience"),
        max_length=20,
        choices=Audience.choices,
        default=Audience.MEMBER,
        help_text="Minimum audience needed to see this area at all.",
    )
    feature_flag = models.CharField(
        _("Feature flag"),
        max_length=50,
        blank=True,
        help_text="Config key that must be enabled for this area to appear, e.g. 'FEATURE_AWARDS'.",
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text="Uncheck to hide the area without deleting it.",
    )

    objects = FeatureAreaQuerySet.as_manager()

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "Feature Area"
        verbose_name_plural = "Feature Areas"

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        try:
            validate_audience(self.audience)
        except ValidationError as error:
            raise ValidationError({"audience": error}) from error


class FeatureQuerySet(models.QuerySet):
    def active(self):
        """Active features that also sit in an active area.

        Deactivating an area hides everything inside it, so callers never have
        to check both flags.
        """
        return self.filter(is_active=True, area__is_active=True)


class Feature(TimeStampedModel):
    """One thing a user can do, described for the catalog.

    A feature points at its destination either through :attr:`url_name` (a named
    Django URL, Viewflow namespaces included) or :attr:`external_url` for the
    handful of features that live outside this application. The two are mutually
    exclusive. Either may be blank -- a feature that only explains something is
    still worth cataloguing.

    :attr:`audience` and :attr:`feature_flag` inherit from the area when blank;
    use :attr:`effective_audience` and :attr:`effective_feature_flag` rather than
    reading the raw fields.
    """

    area = models.ForeignKey(
        FeatureArea,
        on_delete=models.CASCADE,
        related_name="features",
        verbose_name=_("Area"),
    )
    key = models.SlugField(
        _("Key"),
        max_length=100,
        unique=True,
        help_text="Stable identifier used by the registry fixture. Do not rename.",
    )
    name = models.CharField(_("Name"), max_length=150)
    short_description = models.CharField(
        _("Short description"),
        max_length=300,
        help_text="One-line copy for the catalog card.",
    )
    long_description = models.TextField(
        _("Long description"),
        blank=True,
        help_text="Expanded help copy shown when the card is opened.",
    )
    url_name = models.CharField(
        _("URL name"),
        max_length=200,
        blank=True,
        help_text=(
            "Named URL to deep link to, namespaces included, "
            "e.g. 'forms:pledgeform' or 'viewflow:forms:hseducation:start'."
        ),
    )
    external_url = models.URLField(
        _("External URL"),
        max_length=500,
        blank=True,
        help_text="For features hosted outside this application. Cannot be combined with a URL name.",
    )
    url_kwargs = models.JSONField(
        _("URL keyword arguments"),
        default=dict,
        blank=True,
        help_text=(
            "Arguments for the named URL. Values may be the dynamic tokens "
            "'@chapter_slug', '@region_slug' or '@username', resolved per viewer."
        ),
    )
    url_fragment = models.CharField(
        _("URL fragment"),
        max_length=100,
        blank=True,
        help_text=(
            "Element id to scroll to on the destination page, without the '#'. "
            "Use when the feature is a control on a larger page rather than a page of its own."
        ),
    )
    audience = models.CharField(
        _("Audience"),
        max_length=20,
        choices=Audience.choices,
        blank=True,
        help_text="Leave blank to inherit the area's audience.",
    )
    roles = models.JSONField(
        _("Roles"),
        default=list,
        blank=True,
        help_text="Duty roles this feature belongs to, e.g. ['treasurer']. Targeting only, never access control.",
    )
    feature_flag = models.CharField(
        _("Feature flag"),
        max_length=50,
        blank=True,
        help_text="Leave blank to inherit the area's feature flag.",
    )
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        related_name="features",
        null=True,
        blank=True,
        verbose_name=_("Task"),
        help_text="The recurring obligation this feature satisfies, if any.",
    )
    order = models.PositiveSmallIntegerField(
        _("Order"),
        default=0,
        help_text="Display order within the area; lower sorts first.",
    )
    released_at = models.DateField(
        _("Released"),
        null=True,
        blank=True,
        help_text="Release date; drives the What's New feed.",
    )
    release_version = models.CharField(
        _("Release version"),
        max_length=20,
        blank=True,
        help_text="e.g. '2026.03'.",
    )
    is_highlighted = models.BooleanField(
        _("Highlighted"),
        default=False,
        help_text="Show a NEW badge on the catalog card.",
    )
    is_active = models.BooleanField(
        _("Active"),
        default=True,
        help_text="Uncheck to hide the feature without deleting it.",
    )

    objects = FeatureQuerySet.as_manager()

    class Meta:
        ordering = ["area__order", "order", "name"]
        verbose_name = "Feature"
        verbose_name_plural = "Features"

    def __str__(self):
        return self.name

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
        if self.url_name and self.external_url:
            message = _("Set either a URL name or an external URL, not both.")
            errors["url_name"] = message
            errors["external_url"] = message
        if errors:
            raise ValidationError(errors)

    @property
    def effective_audience(self):
        """This feature's audience, falling back to the area's."""
        return self.audience or self.area.audience

    @property
    def effective_feature_flag(self):
        """This feature's flag, falling back to the area's."""
        return self.feature_flag or self.area.feature_flag


class Cadence(models.TextChoices):
    """How often a role-guide step comes round."""

    ONCE = "once", _("Once, when you take office")
    EACH_TERM = "each_term", _("Every term")
    ANNUAL = "annual", _("Once a year")
    ONGOING = "ongoing", _("Ongoing")


class RoleGuideQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class RoleGuide(TimeStampedModel):
    """What one duty role is responsible for (TWI-12).

    Keyed on the same vocabulary as ``tasks.Task.owner``, which is what lets a
    guide show a new officer their real, dated obligations instead of a second
    hand-written checklist that would immediately drift.
    """

    role = models.CharField(
        _("Role"),
        max_length=50,
        unique=True,
        choices=ALL_ROLES_CHOICES,
        help_text="Duty role this guide is for. Must match tasks.Task.owner exactly.",
    )
    slug = models.SlugField(
        _("Slug"),
        max_length=60,
        unique=True,
        blank=True,
        help_text="URL segment; set automatically from the role.",
    )
    title = models.CharField(_("Title"), max_length=150)
    summary = models.TextField(
        _("Summary"),
        help_text="Two to four sentences orienting someone who just took the office.",
    )
    order = models.PositiveSmallIntegerField(_("Order"), default=0)
    is_active = models.BooleanField(_("Active"), default=True)

    objects = RoleGuideQuerySet.as_manager()

    class Meta:
        ordering = ["order", "title"]
        verbose_name = "Role Guide"
        verbose_name_plural = "Role Guides"

    def __str__(self):
        return self.title

    def clean(self):
        # Derive here as well as in `save()` so `full_clean()` can check the slug
        # for uniqueness -- the fixture loader validates before it writes.
        super().clean()
        self.slug = slugify(self.role)

    def save(self, *args, **kwargs):
        self.slug = slugify(self.role)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("guides:role-guide", kwargs={"slug": self.slug})


class RoleGuideStep(TimeStampedModel):
    """One "first thing to do" in a role guide.

    A step is copy, or a pointer to a catalog :class:`Feature`, or a pointer to
    the recurring :class:`tasks.Task` that already tracks the obligation -- or
    any combination. Both pointers are ``SET_NULL``: retiring a feature must not
    silently delete the paragraph explaining the duty.
    """

    guide = models.ForeignKey(
        RoleGuide,
        on_delete=models.CASCADE,
        related_name="steps",
        verbose_name=_("Guide"),
    )
    order = models.PositiveSmallIntegerField(_("Order"), default=0)
    title = models.CharField(_("Title"), max_length=200)
    body = models.TextField(_("Body"), blank=True)
    feature = models.ForeignKey(
        Feature,
        on_delete=models.SET_NULL,
        related_name="role_guide_steps",
        null=True,
        blank=True,
        verbose_name=_("Feature"),
        help_text="Catalog entry this step sends the officer to.",
    )
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        related_name="role_guide_steps",
        null=True,
        blank=True,
        verbose_name=_("Task"),
        help_text="Recurring obligation, so the step can show live due dates.",
    )
    cadence = models.CharField(
        _("Cadence"),
        max_length=20,
        choices=Cadence.choices,
        blank=True,
    )

    class Meta:
        ordering = ["guide__order", "order", "id"]
        verbose_name = "Role Guide Step"
        verbose_name_plural = "Role Guide Steps"

    def __str__(self):
        return f"{self.guide.role} #{self.order}: {self.title}"


class UserAcknowledgement(models.Model):
    """That a user has said "got it" to one announcement or new feature (TWI-6).

    One table for both kinds, so a dismiss behaves identically wherever it
    appears and there is a single endpoint behind it. A generic foreign key is
    the established pattern here (``tasks.TaskChapter.submission_object``).

    Never filter *through* the generic key -- it cannot use an index. Build the
    candidate id list per kind, then subtract with one
    ``values_list("object_id", flat=True)`` query per content type.
    """

    class Source(models.TextChoices):
        MODAL = "modal", _("What's New modal")
        BADGE = "badge", _("NEW badge")
        VISITED = "visited", _("Followed the link")
        BULK = "bulk", _("Dismissed all")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="acknowledgements",
        verbose_name=_("User"),
    )
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(app_label="guides", model="feature")
        | models.Q(app_label="announcements", model="announcement"),
        verbose_name=_("Content type"),
    )
    object_id = models.PositiveIntegerField(_("Object ID"))
    target = GenericForeignKey("content_type", "object_id")
    source = models.CharField(
        _("Source"),
        max_length=20,
        choices=Source.choices,
        blank=True,
        help_text="Which affordance the user used. Feeds the adoption metrics.",
    )
    acknowledged_at = models.DateTimeField(_("Acknowledged at"), auto_now_add=True)

    class Meta:
        ordering = ["-acknowledged_at"]
        unique_together = ("user", "content_type", "object_id")
        indexes = [models.Index(fields=["user", "content_type"])]
        verbose_name = "User Acknowledgement"
        verbose_name_plural = "User Acknowledgements"

    def __str__(self):
        return f"{self.user} acknowledged {self.content_type.model} {self.object_id}"
