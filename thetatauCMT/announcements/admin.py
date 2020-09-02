from django.contrib import admin
from .models import Announcement


class AnnouncementAdmin(admin.ModelAdmin):
    fields = ["title", "priority", "publish_start", "publish_end", "content"]
    list_display = (
        "title",
        "priority",
        "publish_start",
        "publish_end",
        "created",
    )
    list_filter = [
        "priority",
        "publish_start",
        "publish_end",
        "created",
    ]
    search_fields = ("title", "content")
    ordering = [
        "-created",
    ]


admin.site.register(Announcement, AnnouncementAdmin)
