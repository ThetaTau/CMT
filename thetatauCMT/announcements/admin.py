from django.contrib import admin

from .models import Announcement


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    fields = [
        "title",
        "priority",
        "publish_start",
        "publish_end",
        "audience",
        "roles",
        "dismissible",
        "feature",
        "content",
    ]
    list_display = (
        "title",
        "priority",
        "publish_start",
        "publish_end",
        "audience",
        "dismissible",
        "created",
    )
    list_filter = [
        "priority",
        "audience",
        "dismissible",
        "publish_start",
        "publish_end",
        "created",
    ]
    autocomplete_fields = ["feature"]
    search_fields = ("title", "content")
    ordering = [
        "-created",
    ]
