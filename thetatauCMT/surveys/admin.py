from django.contrib import admin
from core.admin import user_chapter
from survey.admin import Survey as Survey_orig, SurveyAdmin, Response, ResponseAdmin
from .models import DepledgeSurvey, Survey


class DepledgeSurveyAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = (
        "user",
        user_chapter,
        "reason",
        "decided",
        "created",
    )
    list_filter = [
        "decided",
        "contact",
        "reason",
        "created",
        "user__chapter",
    ]
    search_fields = ("user__name", "user__username")
    ordering = [
        "-created",
    ]


admin.site.register(DepledgeSurvey, DepledgeSurveyAdmin)

admin.site.unregister(Survey_orig)
admin.site.register(Survey, SurveyAdmin)

admin.site.unregister(Response)
admin.site.register(Response, ResponseAdmin)
