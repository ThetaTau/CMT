from django.contrib import admin
from .models import Submission, GearArticle


class SubmissionAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("name", "date", "type", "user")
    list_filter = ["chapter", "type"]
    ordering = [
        "-date",
    ]


admin.site.register(Submission, SubmissionAdmin)


def submission_chapter(obj):
    return obj.submission.chapter


def submission_date(obj):
    return obj.submission.date


def submission_title(obj):
    return obj.submission.name


class GearArticleAdmin(admin.ModelAdmin):
    raw_id_fields = ["authors"]
    list_display = (
        submission_chapter,
        submission_date,
        submission_title,
        "reviewed",
        "notes",
    )
    list_filter = [
        "submission__date",
        "submission__chapter",
    ]
    ordering = [
        "-submission__date",
    ]


admin.site.register(GearArticle, GearArticleAdmin)
