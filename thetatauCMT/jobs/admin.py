from django.contrib import admin

from .models import Job, JobSearch


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "priority",
        "publish_start",
        "publish_end",
        "created",
        "created_by",
    )
    list_filter = [
        "priority",
        "publish_start",
        "publish_end",
        "created",
    ]
    search_fields = ("title", "description")
    ordering = [
        "-created",
    ]
    raw_id_fields = ("location", "country")
    readonly_fields = ("created_by",)


@admin.register(JobSearch)
class JobSearchAdmin(admin.ModelAdmin):
    list_display = (
        "search_title",
        "created_by",
        "created",
        "modified",
    )
    list_filter = [
        "created",
        "modified",
    ]
    search_fields = ("search_title",)
    ordering = [
        "-created",
    ]
    raw_id_fields = ("location", "country")
