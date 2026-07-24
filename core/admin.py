from address.admin import UnidentifiedListFilter
from address.models import AddressField
from django.conf import settings
from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.text import capfirst
from herald.admin import SentNotificationAdmin
from report_builder.admin import ReportAdmin


def user_chapter(obj):
    return obj.user.chapter


def user(obj):
    user = ""
    if hasattr(obj, "user"):
        user = obj.user.name
    elif hasattr(obj, "user_set"):
        user = ", ".join(obj.user_set.values_list("name", flat=True))
    return user


def chapter(obj):
    chapters = ""
    if hasattr(obj, "chapter_set"):
        chapters = ", ".join(obj.chapter_set.values_list("name", flat=True))
    return chapters


class ReportAdminSync(ReportAdmin):
    ReportAdmin.list_display += ("sync_mail",)

    @admin.display(description="Email Sync")
    def sync_mail(self, model_object):
        return mark_safe(
            f'<a href="{reverse("users:sync_email_provider", kwargs={"report_id": model_object.id})}"'
            f" onclick=\"alert('Start sync with email provider, limit is 2000 every 10 seconds, this may take some time...');\">"
            '<img style="width: 26px; margin: -6px" src="'
            f'{getattr(settings, "STATIC_URL", "/static/")}report_builder/img/reorder.svg"/></a>'
        )


class SentNotificationAdminUpdate(SentNotificationAdmin):
    raw_id_fields = ["user"]


def city(obj):
    return obj.locality


def state(obj):
    state = ""
    if obj.locality:
        state = obj.locality.state
    return state


class UnidentifiedNoUserListFilter(UnidentifiedListFilter):
    title = "missing"
    parameter_name = "unidentified"

    def lookups(self, request, model_admin):
        return (
            ("unidentified", "unidentified"),
            ("nouser", "No Users"),
            ("withuser", "With Users"),
        )

    def queryset(self, request, queryset):
        if self.value() == "unidentified":
            return queryset.filter(locality=None)
        if self.value() == "nouser":
            return queryset.filter(user__isnull=True)
        if self.value() == "withuser":
            return queryset.filter(user__isnull=False)


class ChapterPresenceListFilter(admin.SimpleListFilter):
    title = "chapters"
    parameter_name = "chapters"

    def lookups(self, request, model_admin):
        return (
            ("nochapter", "No Chapters"),
            ("withchapter", "With Chapters"),
        )

    def queryset(self, request, queryset):
        if self.value() == "nochapter":
            return queryset.filter(chapter__isnull=True)
        if self.value() == "withchapter":
            return queryset.filter(chapter__isnull=False).distinct()


class ComponentAddressAdminMixin:
    """Render ``address.models.AddressField`` columns with ``ComponentAddressField``.

    django-address's default form field resolves the submitted value to an
    ``Address`` via ``Address.objects.get(...)`` inside its ``to_python`` /
    ``_to_python``.  When duplicate ``Address`` rows exist that lookup raises
    ``MultipleObjectsReturned`` and the admin change form 500s (issue #815).
    ``ComponentAddressField`` funnels through ``get_or_create_address``, which
    returns the oldest matching row instead of raising, so any admin editing an
    address stays crash-safe even with duplicate rows already in the table.
    """

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, AddressField):
            from core.forms import ComponentAddressField

            return ComponentAddressField(
                required=not db_field.blank,
                label=capfirst(db_field.verbose_name),
                help_text=db_field.help_text,
            )
        return super().formfield_for_dbfield(db_field, request, **kwargs)


class AddressAdmin(admin.ModelAdmin):
    raw_id_fields = ["locality"]
    list_display = ("raw", user, chapter, city, state)
    search_fields = ("street_number", "route", "raw", "user__username", "chapter__name")
    list_filter = (
        UnidentifiedNoUserListFilter,
        ChapterPresenceListFilter,
        "locality__state__name",
        "user__chapter",
        "chapter",
    )
