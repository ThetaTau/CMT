from django.contrib import admin

from .models import AttendanceRecord, AttendanceStatusTransition, MatchQueueItem


class AttendanceStatusTransitionInline(admin.TabularInline):
    model = AttendanceStatusTransition
    extra = 0
    fields = ("from_status", "to_status", "changed_by", "changed_at")
    readonly_fields = ("from_status", "to_status", "changed_by", "changed_at")
    can_delete = False


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "event",
        "status",
        "was_active",
        "chapter",
        "recorded_by",
        "recorded_at",
    )
    list_filter = ("status", "was_active", "chapter")
    search_fields = ("user__name", "event__name")
    autocomplete_fields = ("event", "user", "chapter", "recorded_by")
    readonly_fields = ("previous_status", "transitioned_at")
    inlines = [AttendanceStatusTransitionInline]


@admin.register(AttendanceStatusTransition)
class AttendanceStatusTransitionAdmin(admin.ModelAdmin):
    list_display = ("record", "from_status", "to_status", "changed_by", "changed_at")
    list_filter = ("to_status",)
    search_fields = ("record__user__name", "record__event__name")


@admin.register(MatchQueueItem)
class MatchQueueItemAdmin(admin.ModelAdmin):
    """Review queue for national-event attendance rows that could not be
    auto-matched (WI-7). Manual resolution is normally done in the dedicated
    queue UI; this admin exposes the raw rows, candidate scores, and audit
    trail, plus a bulk 'skip' action.
    """

    list_display = (
        "display_label",
        "event",
        "status",
        "best_score",
        "raw_email",
        "raw_chapter",
        "resolved_user",
        "created",
    )
    list_filter = ("status", "event")
    search_fields = ("raw_name", "raw_email", "raw_member_id", "raw_badge_number", "event__name")
    autocomplete_fields = ("event", "resolved_user", "resolved_by", "uploaded_by", "attendance_record")
    readonly_fields = (
        "upload_id",
        "fingerprint",
        "candidates",
        "best_score",
        "raw_row",
        "resolved_user",
        "attendance_record",
        "resolved_by",
        "resolved_at",
        "uploaded_by",
    )
    actions = ["mark_skipped"]

    @admin.action(description="Mark selected rows as skipped")
    def mark_skipped(self, request, queryset):
        updated = 0
        for item in queryset.filter(status=MatchQueueItem.Status.PENDING):
            item.skip(request.user)
            updated += 1
        self.message_user(request, f"Skipped {updated} pending row(s).")
