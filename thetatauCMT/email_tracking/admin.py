from django.contrib import admin

from .models import EmailTrackingEvent, TrackedEmail


class EmailTrackingEventInline(admin.TabularInline):
    model = EmailTrackingEvent
    extra = 0
    can_delete = False
    fields = ("event_type", "timestamp", "click_url", "user_agent", "reject_reason")
    readonly_fields = fields
    ordering = ("-timestamp", "-created")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(TrackedEmail)
class TrackedEmailAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "recipient",
        "user",
        "last_status",
        "open_count",
        "click_count",
        "first_opened_at",
        "sent_at",
    )
    list_filter = ("esp", "last_status", "sent_at")
    search_fields = (
        "recipient",
        "subject",
        "message_id",
        "user__username",
        "user__name",
    )
    date_hierarchy = "sent_at"
    autocomplete_fields = ("user",)
    raw_id_fields = ("sent_notification",)
    inlines = (EmailTrackingEventInline,)
    readonly_fields = (
        "esp",
        "message_id",
        "recipient",
        "subject",
        "from_email",
        "tags",
        "metadata",
        "sent_notification",
        "notification_class",
        "sent_at",
        "last_status",
        "delivered_at",
        "first_opened_at",
        "last_opened_at",
        "open_count",
        "first_clicked_at",
        "last_clicked_at",
        "click_count",
        "bounced_at",
        "complained_at",
        "unsubscribed_at",
        "reject_reason",
        "created",
        "modified",
    )

    def has_add_permission(self, request):
        return False


@admin.register(EmailTrackingEvent)
class EmailTrackingEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_type",
        "recipient",
        "timestamp",
        "message_id",
        "click_url",
        "reject_reason",
    )
    list_filter = ("esp", "event_type", "timestamp")
    search_fields = ("recipient", "message_id", "click_url")
    date_hierarchy = "timestamp"
    raw_id_fields = ("tracked_email",)
    readonly_fields = (
        "tracked_email",
        "esp",
        "message_id",
        "recipient",
        "event_type",
        "timestamp",
        "click_url",
        "user_agent",
        "reject_reason",
        "mta_response",
        "tags",
        "metadata",
        "raw",
        "created",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
