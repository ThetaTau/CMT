from django.contrib import admin
from django.http import HttpResponseRedirect
from django.shortcuts import render
from .models import Training
from .forms import UserAdminTrainingForm


class AssignTrainingMixin:
    def assign_training(self, request, queryset):
        extra_groups = Training.get_extra_groups()
        kwargs = {
            "extra_groups": extra_groups,
            "initial": {"_selected_action": queryset.values_list("id", flat=True)},
        }
        if request.method in ("POST", "PUT"):
            kwargs.update(
                {
                    "data": request.POST,
                }
            )
        form = UserAdminTrainingForm(**kwargs)
        if "apply" in request.POST:
            if form.is_valid() and not form.errors:
                for user in queryset:
                    extra_group = form.cleaned_data["extra_group"]
                    Training.add_user(user, extra_group=extra_group, request=request)
                return HttpResponseRedirect(request.get_full_path())
        return render(
            request,
            "admin/assign_training.html",
            context={"form": form},
        )

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
