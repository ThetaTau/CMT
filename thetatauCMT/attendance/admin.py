from django.contrib import admin

from .models import AttendanceRecord, AttendanceStatusTransition


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
