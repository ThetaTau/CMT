from django.contrib import admin

from .models import Job, JobSearch


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


admin.site.register(JobSearch, JobSearchAdmin)
admin.site.register(Job, JobAdmin)
