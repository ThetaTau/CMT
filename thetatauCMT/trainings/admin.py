import logging

from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render

from .forms import EdCourseAdminForm, UserAdminTrainingForm
from .models import EdCourse, Training

logger = logging.getLogger(__name__)


class AssignTrainingMixin:
    @admin.action(description="Assign Member Training")
    def assign_training(self, request, queryset):
        try:
            extra_groups = Training.get_extra_groups()
        except Exception:
            extra_groups = [
                ("NONE", "NONE"),
            ]
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
                extra_group = form.cleaned_data["extra_group"]
                training_system = form.cleaned_data["training_system"]
                ed_courses = [course.course_id for course in form.cleaned_data["ed_courses"]]
                ed_header = None
                if training_system == "ED.thetatau":
                    # One Open edX token for the whole batch.
                    try:
                        ed_header = Training._ed_authenticate_header()
                    except Exception:
                        logger.exception("Open edX authentication failed for the Assign Member Training action")
                        self.message_user(
                            request,
                            "Could not sign in to Open edX with ED_ID/ED_SECRET, so nobody was enrolled.",
                            level=messages.ERROR,
                        )
                        return HttpResponseRedirect(request.get_full_path())
                for user in queryset:
                    # A training-system outage must not abort the whole bulk
                    # action or return a 500; log it, tell the admin, and keep
                    # processing the remaining users.
                    try:
                        if training_system == "Vector":
                            Training.add_user(user, extra_group=extra_group, request=request)
                        elif training_system == "ED.thetatau":
                            Training.enroll_user_ed(user, courses=ed_courses, header=ed_header, request=request)
                    except Exception:
                        logger.exception("Training assignment failed for %s", user)
                        self.message_user(
                            request,
                            f"Training assignment failed for {user}; it was skipped. See logs for details.",
                            level=messages.ERROR,
                        )
                return HttpResponseRedirect(request.get_full_path())
        return render(
            request,
            "admin/assign_training.html",
            context={"form": form},
        )


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


@admin.register(Training)
class TrainingAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "course_title", "completed", "completed_time")
    list_filter = ["course_title", "completed", "completed_time"]
    ordering = [
        "-completed_time",
    ]


@admin.register(EdCourse)
class EdCourseAdmin(admin.ModelAdmin):
    form = EdCourseAdminForm
    list_display = ("title", "course_id", "active", "assign_to_all_members", "roles_display")
    list_filter = ("active", "assign_to_all_members")
    search_fields = ("title", "course_id")

    @admin.display(description="Assign to roles")
    def roles_display(self, obj):
        return "; ".join(role.title() for role in obj.assign_to_roles) or "None"
