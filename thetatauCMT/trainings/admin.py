from django.contrib import admin
from .models import Training


class AssignTrainingMixin:
    def assign_training(self, request, queryset):
        for user in queryset:
            Training.add_user(user, request=request)

    assign_training.short_description = "Assign Member Training"


class TrainingInline(admin.TabularInline):
    model = Training
    raw_id_fields = ["user"]
    readonly_fields = [
        "user",
        "course_title",
        "completed",
        "completed_time",
        "max_quiz_score",
    ]
    fields = ["user", "course_title", "completed", "completed_time", "max_quiz_score"]
    show_change_link = True
    can_delete = False
    ordering = ["-completed_time"]
    extra = 0

    def has_add_permission(self, _, obj=None):
        return False


class TrainingAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "course_title", "completed", "completed_time")
    list_filter = ["course_title", "completed", "completed_time"]
    ordering = [
        "-completed_time",
    ]


admin.site.register(Training, TrainingAdmin)
