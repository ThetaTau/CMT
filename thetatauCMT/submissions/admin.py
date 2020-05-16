from django.contrib import admin
from .models import Submission


class SubmissionAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("name", "date", "type", "user")
    list_filter = ["chapter", "type"]
    ordering = [
        "-date",
    ]


admin.site.register(Submission, SubmissionAdmin)
