from django.conf import settings
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.urls import reverse
from report_builder.admin import ReportAdmin
from herald.admin import SentNotificationAdmin, SentNotification
from address.admin import UnidentifiedListFilter


def user_chapter(obj):
    return obj.user.chapter


def user(obj):
    user = ""
    if hasattr(obj, "user"):
        user = obj.user.name
    elif hasattr(obj, "user_set"):
        user = ", ".join(obj.user_set.values_list("name", flat=True))
    return user


class ReportAdminSync(ReportAdmin):
    ReportAdmin.list_display += ("sync_mail",)

    def sync_mail(self, model_object):
        return mark_safe(
            f'<a href="{reverse("users:sync_email_provider", kwargs={"report_id": model_object.id})}"'
            f" onclick=\"alert('Start sync with email provider, limit is 2000 every 10 seconds, this may take some time...');\">"
            '<img style="width: 26px; margin: -6px" src="'
            f'{getattr(settings, "STATIC_URL", "/static/")}report_builder/img/reorder.svg"/></a>'
        )

    sync_mail.short_description = "Email Sync"
    sync_mail.allow_tags = True


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


class AddressAdmin(admin.ModelAdmin):
    raw_id_fields = ["locality"]
    list_display = ("raw", user, city, state)
    search_fields = ("street_number", "route", "raw", "user__username")
    list_filter = (
        UnidentifiedNoUserListFilter,
        "locality__state__name",
        "user__chapter",
    )
