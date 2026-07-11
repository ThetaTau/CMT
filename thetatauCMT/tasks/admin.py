from django.contrib import admin
from django.utils import timezone

from .models import Task, TaskChapter, TaskDate


class TaskChapterInline(admin.TabularInline):
    model = TaskChapter
    fields = ["date", "chapter", "submission_type", "submission_id"]
    show_change_link = True
    ordering = ["date"]
    extra = 1


@admin.register(TaskDate)
class TaskDateAdmin(admin.ModelAdmin):
    inlines = [TaskChapterInline]
    list_display = ("task", "date", "school_type", "archived")
    list_filter = ["archived", "school_type", "date"]
    actions = ["mark_no_longer_needed", "restore_dates"]
    ordering = [
        "date",
    ]

    @admin.action(description="Mark selected due dates as no longer needed")
    def mark_no_longer_needed(self, request, queryset):
        updated = queryset.filter(archived=False).update(
            archived=True,
            archived_on=timezone.now(),
            archived_reason="Marked no longer needed via admin",
        )
        self.message_user(request, f"{updated} due date(s) marked as no longer needed.")

    @admin.action(description="Restore selected due dates")
    def restore_dates(self, request, queryset):
        updated = queryset.filter(archived=True).update(
            archived=False,
            archived_on=None,
            archived_reason="",
        )
        self.message_user(request, f"{updated} due date(s) restored.")


class TaskDateInline(admin.TabularInline):
    model = TaskDate
    fields = ["school_type", "date", "archived"]
    show_change_link = True
    ordering = ["date"]
    extra = 1


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    inlines = [TaskDateInline]
    list_display = (
        "name",
        "owner",
        "type",
        "submission_type",
        "resource",
        "days_advance",
    )
    list_filter = ["owner", "type"]
    ordering = [
        "name",
    ]


@admin.register(TaskChapter)
class TaskChapterAdmin(admin.ModelAdmin):
    list_display = ("task", "chapter", "date", "submission_type")
    list_filter = ["chapter", "date"]
    ordering = [
        "date",
    ]
    readonly_fields = (
        "created_by",
        "modified_by",
    )
