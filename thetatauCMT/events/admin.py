from django.contrib import admin

from thetatauCMT.attendance.models import AttendanceRecord

from .models import Event

# Register your models here.


class SubEventInline(admin.TabularInline):
    """Child sub-events shown inline on their parent event."""

    model = Event
    fk_name = "parent_event"
    extra = 0
    fields = ("name", "date", "type", "chapter", "is_public", "is_national", "approval_status")
    autocomplete_fields = ("type", "chapter")
    show_change_link = True
    verbose_name = "Sub-event"
    verbose_name_plural = "Sub-events"


class EventAttendanceInline(admin.TabularInline):
    """Attendance records for an event. Member is an autocomplete (30K+ members)."""

    model = AttendanceRecord
    extra = 0
    fields = ("user", "status", "was_active", "chapter", "recorded_by", "recorded_at")
    autocomplete_fields = ("user", "chapter", "recorded_by")
    readonly_fields = ("recorded_at",)
    show_change_link = True


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "date",
        "chapter",
        "type",
        "is_public",
        "is_national",
        "approval_status",
        "deleted",
        "parent_event",
        "description",
    )
    list_filter = ["deleted", "approval_status", "is_public", "is_national", "chapter", "type"]
    search_fields = ("name",)
    autocomplete_fields = ("parent_event",)
    inlines = [SubEventInline, EventAttendanceInline]
    actions = ["soft_delete_events", "restore_events"]
    ordering = [
        "date",
    ]
    readonly_fields = (
        "created_by",
        "modified_by",
        "reviewed_by",
        "reviewed_at",
        "deleted_at",
        "deleted_by",
    )

    def get_queryset(self, request):
        # Show soft-deleted events in the admin so they can be reviewed/restored.
        return self.model.all_objects.get_queryset()

    @admin.action(description="Soft-delete selected events (remove from scoring)")
    def soft_delete_events(self, request, queryset):
        count = 0
        for event in queryset.filter(deleted=False):
            event.soft_delete(request.user)
            count += 1
        self.message_user(request, f"Soft-deleted {count} event(s).")

    @admin.action(description="Restore selected soft-deleted events")
    def restore_events(self, request, queryset):
        count = 0
        for event in queryset.filter(deleted=True):
            event.restore(request.user)
            count += 1
        self.message_user(request, f"Restored {count} event(s).")

    def view_on_site(self, obj):
        # Return the relative URL so the admin "View on site" link resolves
        # against the current host (e.g. localhost in local development) instead
        # of the Sites-framework domain (cmt.thetatau.org).
        return obj.get_absolute_url()
