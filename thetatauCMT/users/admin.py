import csv
import datetime
from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.utils.html import escape
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib.auth.models import Permission
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.forms import UserChangeForm
from import_export.admin import ImportExportActionModelAdmin, ImportMixin
from report_builder.admin import Report
from address.admin import Address
from simple_history.admin import SimpleHistoryAdmin
from .forms import UserAdminStatusForm, UserAdminBadgeFixForm
from .models import (
    User,
    Role,
    UserRoleChange,
    UserStatusChange,
    UserOrgParticipate,
    UserSemesterGPA,
    UserSemesterServiceHours,
    UserAlter,
    ChapterCurricula,
    UserDemographic,
    MemberUpdate,
)
from .resources import UserRoleChangeResource, UserResource, UserStatusChangeResource
from .views import ExportActiveMixin
from forms.models import (
    Depledge,
    Initiation,
    StatusChange,
    CollectionReferral,
    DisciplinaryProcess,
    OSM,
    PrematureAlumnus,
    ResignationProcess,
    ReturnStudent,
)
from core.admin import (
    user_chapter,
    ReportAdminSync,
    SentNotificationAdminUpdate,
    SentNotification,
    AddressAdmin,
)
from notes.admin import UserNoteInline, UserNote
from trainings.admin import AssignTrainingMixin, TrainingInline
from core.signals import SignalWatchMixin
from core.models import forever

admin.site.register(Permission)
admin.site.unregister(Report)
admin.site.register(Report, ReportAdminSync)
admin.site.unregister(SentNotification)
admin.site.register(SentNotification, SentNotificationAdminUpdate)
admin.site.unregister(Address)
admin.site.register(Address, AddressAdmin)


class UserStatusChangeAdmin(ImportExportActionModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "status", "created", user_chapter, "start", "end")
    list_filter = ["status", "created", "user__chapter", "start", "end"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__name"]
    resource_class = UserStatusChangeResource


admin.site.register(UserStatusChange, UserStatusChangeAdmin)


class UserDemographicAdmin(admin.ModelAdmin):
    exclude = ("user",)
    list_display = (
        user_chapter,
        "gender",
        "sexual",
        "racial",
        "ability",
        "first_gen",
        "english",
    )
    list_filter = [
        "user__chapter",
        "gender",
        "sexual",
        "racial",
        "ability",
        "first_gen",
        "english",
    ]
    search_fields = ["user__chapter"]


admin.site.register(UserDemographic, UserDemographicAdmin)


class UserOrgParticipateAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "org_name", "type", "officer", "start", "end")
    list_filter = ["start", "end", "officer", "type"]
    ordering = [
        "-start",
    ]


admin.site.register(UserOrgParticipate, UserOrgParticipateAdmin)


class UserSemesterGPAAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "gpa", "year", "term")
    list_filter = ["year", "term"]
    ordering = [
        "-year",
    ]


admin.site.register(UserSemesterGPA, UserSemesterGPAAdmin)


class UserSemesterServiceHoursAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "service_hours", "year", "term")
    list_filter = ["year", "term"]
    ordering = [
        "-year",
    ]


admin.site.register(UserSemesterServiceHours, UserSemesterServiceHoursAdmin)


class MemberInline(admin.TabularInline):
    model = User
    fields = ["name", "user_id"]
    readonly_fields = ("name", "user_id")
    can_delete = False
    ordering = ["name"]
    show_change_link = True

    def has_add_permission(self, _, obj=None):
        return False


class RoleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "officer",
        "executive_council",
        "chapter",
        "national",
        "alumni",
        "foundation",
        "central_office",
    )
    list_filter = [
        "officer",
        "executive_council",
        "chapter",
        "national",
        "alumni",
        "foundation",
        "central_office",
    ]
    ordering = [
        "name",
    ]


admin.site.register(Role, RoleAdmin)


class UserRoleChangeAdmin(ImportExportActionModelAdmin):
    list_display = ("user", "role_link", "start", "end", "created", user_chapter)
    list_filter = ["start", "end", "role_link", "created", "user__chapter"]
    ordering = [
        "-created",
    ]
    raw_id_fields = ["user"]
    resource_class = UserRoleChangeResource


admin.site.register(UserRoleChange, UserRoleChangeAdmin)


class MyUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class MyUserCreationForm(forms.ModelForm):
    class Meta:
        model = User
        # Needs to be duplicated at MyUserAdmin.add_fieldsets
        fields = (
            "first_name",
            "middle_name",
            "last_name",
            "email",
            "chapter",
            "badge_number",
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password("")
        if commit:
            user.save()
        return user


class StatusInline(admin.TabularInline):
    model = UserStatusChange
    fields = ["status", "start", "end"]
    show_change_link = True
    ordering = ["end"]
    extra = 1


class RoleInline(admin.TabularInline):
    model = UserRoleChange
    fields = ["role_link", "start", "end"]
    show_change_link = True
    ordering = ["end"]
    extra = 1


class DepledgeInline(admin.TabularInline):
    model = Depledge
    fields = ["reason", "date", "created"]
    show_change_link = True
    ordering = ["date"]
    extra = 0


class StatusChangeInline(admin.TabularInline):
    model = StatusChange
    fields = ["reason", "date_start", "date_end", "created"]
    show_change_link = True
    ordering = ["date_end"]
    extra = 0


class InitiationInline(admin.TabularInline):
    model = Initiation
    fields = [
        "date",
        "created",
        "roll",
        "date_graduation",
        "chapter",
        "gpa",
        "test_a",
        "test_b",
    ]
    show_change_link = True
    ordering = ["date"]
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class CollectionReferralInline(admin.TabularInline):
    model = CollectionReferral
    fk_name = "user"
    readonly_fields = ("created",)
    fields = [
        "balance_due",
        "ledger_sheet",
    ]
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class DisciplinaryProcessInline(admin.TabularInline):
    model = DisciplinaryProcess
    fk_name = "user"
    readonly_fields = ("created",)
    fields = [
        "charges",
        "trial_date",
        "punishment",
        "ec_approval",
    ]
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class OSMInline(admin.TabularInline):
    model = OSM
    fk_name = "nominate"
    fields = [
        "meeting_date",
        "year",
        "term",
        "selection_process",
    ]
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class PrematureAlumnusInline(admin.TabularInline):
    model = PrematureAlumnus
    fk_name = "user"
    readonly_fields = ("created",)
    fields = [
        "prealumn_type",
        "approved_exec",
        "exec_comments",
    ]
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class ResignationProcessInline(admin.TabularInline):
    model = ResignationProcess
    fk_name = "user"
    readonly_fields = ("created",)
    fields = [
        "approved_o1",
        "approved_o2",
        "approved_exec",
        "exec_comments",
    ]
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class ReturnStudentInline(admin.TabularInline):
    model = ReturnStudent
    fk_name = "user"
    readonly_fields = ("created",)
    fields = [
        "reason",
        "approved_exec",
        "exec_comments",
    ]
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


class UserAlterInline(admin.StackedInline):
    model = UserAlter
    fields = ["chapter", "role"]
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(User)
class MyUserAdmin(
    ImportMixin,
    AuthUserAdmin,
    ExportActiveMixin,
    AssignTrainingMixin,
    SignalWatchMixin,
    SimpleHistoryAdmin,
):
    object_type = "user"
    actions = [
        "export_chapter_actives",
        "assign_training",
        "watch_notification_add",
        "watch_notification_remove",
        "update_status",
        "badge_fix",
    ]
    raw_id_fields = ["address"]
    readonly_fields = (
        "deceased_changed",
        "current_roles",
        "current_status",
        "officer",
    )
    inlines = [
        UserNoteInline,
        UserAlterInline,
        StatusInline,
        RoleInline,
        InitiationInline,
        StatusChangeInline,
        DepledgeInline,
        PrematureAlumnusInline,
        ReturnStudentInline,
        ResignationProcessInline,
        OSMInline,
        DisciplinaryProcessInline,
        CollectionReferralInline,
        TrainingInline,
    ]
    form = MyUserChangeForm
    add_form = MyUserCreationForm
    # Needs to be duplicated at MyUserCreationForm.Meta.fields
    add_fieldsets = (
        (
            None,
            {
                "fields": (
                    "first_name",
                    "middle_name",
                    "last_name",
                    "preferred_name",
                    "email",
                    "chapter",
                    "badge_number",
                ),
            },
        ),
    )
    fieldsets = (
        ("User Profile", {"fields": ("name", "chapter", "badge_number", "user_id")}),
        (None, {"fields": ("username", "password")}),
        (
            _("Personal info"),
            {
                "fields": (
                    "title",
                    "first_name",
                    "middle_name",
                    "last_name",
                    "current_status",
                    "current_roles",
                    "officer",
                    "charter",
                    "no_contact",
                    "address",
                    "deceased",
                    "deceased_date",
                    "deceased_changed",
                    "suffix",
                    "nickname",
                    "preferred_name",
                    "birth_date",
                    "email",
                    "email_school",
                    "phone_number",
                    "major",
                    "employer",
                    "employer_position",
                    "graduation_year",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    list_display = (
        "username",
        "name",
        "last_login",
        "user_id",
        "badge_number",
        "chapter",
        "current_status",
        "current_roles",
        "officer",
    )
    list_filter = (
        "is_superuser",
        "last_login",
        "groups",
        "current_status",
        "officer",
        "chapter",
    )
    search_fields = ("user_id", "badge_number") + AuthUserAdmin.search_fields
    resource_class = UserResource

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "major":
            try:
                user_id = request.resolver_match.kwargs.get("object_id")
                if user_id:
                    user = User.objects.get(id=user_id)
                    kwargs["queryset"] = ChapterCurricula.objects.filter(
                        chapter=user.chapter
                    )
            except IndexError:
                pass
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for instance in instances:
            if isinstance(instance, UserNote):
                user = request.user
                if not change or not hasattr(instance, "created_by"):
                    instance.created_by = user
                instance.modified_by = user
                instance.save()
        formset.save()

    def badge_fix(self, request, queryset):
        if "apply" in request.POST:
            badge_file = request.FILES.get("badge_file")
            decoded_file = badge_file.read().decode("utf-8").splitlines()
            reader = csv.DictReader(decoded_file)
            message = User.fix_badge_numbers(reader)
            self.message_user(request, mark_safe(f"Fix Badge process:<br>{message}"))
            return HttpResponseRedirect(request.get_full_path())
        form = UserAdminBadgeFixForm(
            initial={"_selected_action": queryset.values_list("id", flat=True)}
        )
        return render(
            request,
            "admin/badge_fixes.html",
            context={"form": form},
        )

    badge_fix.short_description = "Fix Badge Numbers"

    def update_status(self, request, queryset):
        if "apply" in request.POST:
            new_status = request.POST.get("status")
            start = request.POST.get("start")
            start = datetime.datetime.strptime(start, "%m/%d/%Y").date()
            end = request.POST.get("end")
            end = datetime.datetime.strptime(end, "%m/%d/%Y").date()
            for user in queryset:
                current_status = user.current_status
                user.set_current_status(new_status, start=start, end=end)
                if end < forever().date():
                    user.set_current_status(current_status, start=end, current=False)
            self.message_user(
                request, f"Set status to {new_status} {start=} {end=} for {queryset}"
            )
            return HttpResponseRedirect(request.get_full_path())
        form = UserAdminStatusForm(
            initial={"_selected_action": queryset.values_list("id", flat=True)}
        )
        return render(
            request,
            "admin/update_status.html",
            context={"form": form},
        )

    update_status.short_description = "Update Status"


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = "action_time"

    list_filter = ["content_type", "action_flag"]

    search_fields = ["object_repr", "change_message"]

    list_display = [
        "action_time",
        "user",
        "content_type",
        "object_link",
        "action_flag",
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def object_link(self, obj):
        if obj.action_flag == DELETION:
            link = escape(obj.object_repr)
        else:
            ct = obj.content_type
            link = '<a href="%s">%s</a>' % (
                reverse(
                    "admin:%s_%s_change" % (ct.app_label, ct.model),
                    args=[obj.object_id],
                ),
                escape(obj.object_repr),
            )
        return mark_safe(link)

    object_link.admin_order_field = "object_repr"
    object_link.short_description = "object"


class MemberUpdateAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = (
        "user",
        "first_name",
        "last_name",
        "chapter",
        "created",
        "approved",
        "outcome",
    )
    list_filter = [
        "outcome",
        "approved",
        "chapter",
    ]
    ordering = [
        "-created",
    ]
    search_fields = ["user__name", "first_name", "last_name"]


admin.site.register(MemberUpdate, MemberUpdateAdmin)
