import csv
import datetime

from address.admin import Address
from django import forms
from django.contrib import admin
from django.contrib.admin.models import DELETION, LogEntry
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import Permission
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from herald.models import SentNotification
from import_export.admin import ImportExportActionModelAdmin, ImportMixin
from report_builder.admin import Report
from simple_history.admin import SimpleHistoryAdmin
from watson.admin import SearchAdmin

from core.admin import AddressAdmin, ReportAdminSync, SentNotificationAdminUpdate, user_chapter
from core.models import forever
from core.signals import SignalWatchMixin
from thetatauCMT.forms.models import (
    OSM,
    AlumniExclusion,
    CollectionReferral,
    Depledge,
    DisciplinaryProcess,
    Initiation,
    PrematureAlumnus,
    ResignationProcess,
    ReturnStudent,
    RitualProficiency,
    StatusChange,
)
from thetatauCMT.notes.admin import UserNote, UserNoteInline
from thetatauCMT.trainings.admin import AssignTrainingMixin, TrainingInline

from .forms import UserAdminBadgeFixForm, UserAdminStatusForm, UserStatusForm, status_options
from .models import (
    ChapterCurricula,
    MemberUpdate,
    User,
    UserAlter,
    UserDemographic,
    UserOrgParticipate,
    UserRoleChange,
    UserSemesterGPA,
    UserSemesterServiceHours,
    UserStatusChange,
    UserTag,
)
from .resources import UserResource, UserRoleChangeResource, UserStatusChangeResource, UserTagResource
from .views import ExportActiveMixin

admin.site.register(Permission)
admin.site.unregister(Report)
admin.site.register(Report, ReportAdminSync)
admin.site.unregister(SentNotification)
admin.site.register(SentNotification, SentNotificationAdminUpdate)
admin.site.unregister(Address)
admin.site.register(Address, AddressAdmin)


def status(obj):
    status = obj.get_status_display()
    if "CC" in obj.status:
        status += " CC"
    return status


@admin.register(UserTag)
class UserTagAdmin(ImportExportActionModelAdmin):
    list_display = ("name", "user_count")
    search_fields = ("name",)
    ordering = ("name",)
    resource_class = UserTagResource

    class UserTagUserInline(admin.TabularInline):
        # Auto-created through table for the User.tags M2M. Lets admins
        # see every user carrying this tag and add more via autocomplete.
        model = User.tags.through
        extra = 1
        verbose_name = "Tagged user"
        verbose_name_plural = "Tagged users"
        autocomplete_fields = ("user",)
        fk_name = "usertag"

    inlines = [UserTagUserInline]

    @admin.display(description="Users", ordering="users__count")
    def user_count(self, obj):
        return obj.users.count()


class StatusListFilter(admin.SimpleListFilter):
    # Human-readable title which will be displayed in the
    # right admin sidebar just above the filter options.
    title = _("Status")

    # Parameter for the filter that will be used in the URL query.
    parameter_name = "status"

    def lookups(self, request, model_admin):
        """
        Returns a list of tuples. The first element in each
        tuple is the coded value for the option that will
        appear in the URL query. The second element is the
        human-readable name for the option that will appear
        in the right sidebar.
        """
        return status_options()

    def queryset(self, request, queryset):
        return queryset.filter(**self.used_parameters)


@admin.register(UserStatusChange)
class UserStatusChangeAdmin(ImportExportActionModelAdmin, SearchAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", status, "created", user_chapter, "start", "end")
    list_filter = [StatusListFilter, "created", "user__chapter", "start", "end"]
    ordering = [
        "-created",
    ]
    form = UserStatusForm
    readonly_fields = (
        "created",
        "user",
        "created_by",
        "modified_by",
    )
    search_fields = [
        "user__name",
        "user__preferred_name",
    ]
    resource_class = UserStatusChangeResource


@admin.register(UserDemographic)
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
    search_fields = ["user__chapter__name"]


@admin.register(UserOrgParticipate)
class UserOrgParticipateAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "org_name", "type", "officer", "start", "end")
    list_filter = ["start", "end", "officer", "type"]
    ordering = [
        "-start",
    ]
    readonly_fields = (
        "created_by",
        "modified_by",
    )


@admin.register(UserSemesterGPA)
class UserSemesterGPAAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "gpa", "year", "term")
    list_filter = ["year", "term"]
    ordering = [
        "-year",
    ]
    readonly_fields = (
        "created_by",
        "modified_by",
    )


@admin.register(UserSemesterServiceHours)
class UserSemesterServiceHoursAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "service_hours", "year", "term")
    list_filter = ["year", "term"]
    ordering = [
        "-year",
    ]
    readonly_fields = (
        "created_by",
        "modified_by",
    )


class MemberInline(admin.TabularInline):
    model = User
    fields = ["name", "username"]
    readonly_fields = ("name", "username")
    can_delete = False
    ordering = ["name"]
    show_change_link = True

    def has_add_permission(self, _, obj=None):
        return False


@admin.register(UserRoleChange)
class UserRoleChangeAdmin(ImportExportActionModelAdmin):
    list_display = ("user", "role", "start", "end", "created", user_chapter)
    list_filter = ["start", "end", "role", "created", "user__chapter"]
    ordering = [
        "-created",
    ]
    raw_id_fields = ["user"]
    resource_class = UserRoleChangeResource


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
    show_change_link = True
    ordering = ["end"]
    extra = 0
    form = UserStatusForm
    fk_name = "user"


class RoleInline(admin.TabularInline):
    model = UserRoleChange
    fields = ["role", "start", "end"]
    show_change_link = True
    ordering = ["end"]
    extra = 1
    fk_name = "user"


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
    fk_name = "user"


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


class AlumniExclusionInline(admin.TabularInline):
    model = AlumniExclusion
    fk_name = "user"
    readonly_fields = ("created", "regional_director")
    fields = [
        "reason",
        "date_start",
        "date_end",
        "voting_result",
        "minutes",
        "regional_director_veto",
        "regional_director",
        "veto_reason",
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


class RitualProficiencyInline(admin.TabularInline):
    model = RitualProficiency
    fk_name = "user"
    readonly_fields = ("recorded_by", "created")
    fields = [
        "level",
        "date",
        "memorization",
        "directions",
        "performance",
        "notes",
        "recorded_by",
    ]
    show_change_link = True
    extra = 0

    def has_add_permission(self, request, obj=None):
        return True


@admin.register(User)
class MyUserAdmin(
    ImportMixin,
    AuthUserAdmin,
    ExportActiveMixin,
    AssignTrainingMixin,
    SignalWatchMixin,
    SimpleHistoryAdmin,
    SearchAdmin,
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
        "id",
    )
    autocomplete_fields = ("tags",)
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
        AlumniExclusionInline,
        CollectionReferralInline,
        RitualProficiencyInline,
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
                    "preferred_pronouns",
                    "preferred_name",
                    "email",
                    "chapter",
                    "badge_number",
                ),
            },
        ),
    )
    fieldsets = (
        ("User Profile", {"fields": ("name", "id", "chapter", "badge_number")}),
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
                    "tags",
                    "charter",
                    "no_contact",
                    "address",
                    "deceased",
                    "deceased_date",
                    "deceased_changed",
                    "unsubscribe_paper_gear",
                    "unsubscribe_email",
                    "suffix",
                    "nickname",
                    "preferred_pronouns",
                    "preferred_name",
                    "birth_date",
                    "email",
                    "email_school",
                    "phone_number",
                    "major",
                    "employer",
                    "employer_position",
                    "graduation_year",
                    "class_year",
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
        "id",
        "name",
        "last_login",
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
    search_fields = (
        "badge_number",
        "id",
        "preferred_name",
        "nickname",
        "email_school",
    ) + AuthUserAdmin.search_fields
    resource_class = UserResource

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "major":
            try:
                user_pk = request.resolver_match.kwargs.get("object_id")
                if user_pk:
                    user = User.objects.get(id=user_pk)
                    kwargs["queryset"] = ChapterCurricula.objects.filter(chapter=user.chapter)
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

    @admin.action(description="Fix Badge Numbers")
    def badge_fix(self, request, queryset):
        if "apply" in request.POST:
            badge_file = request.FILES.get("badge_file")
            decoded_file = badge_file.read().decode("utf-8").splitlines()
            reader = csv.DictReader(decoded_file)
            message = User.fix_badge_numbers(reader)
            self.message_user(request, mark_safe(f"Fix Badge process:<br>{message}"))
            return HttpResponseRedirect(request.get_full_path())
        form = UserAdminBadgeFixForm(initial={"_selected_action": queryset.values_list("id", flat=True)})
        return render(
            request,
            "admin/badge_fixes.html",
            context={"form": form},
        )

    @admin.action(description="Update Status")
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
            self.message_user(request, f"Set status to {new_status} {start=} {end=} for {queryset}")
            return HttpResponseRedirect(request.get_full_path())
        form = UserAdminStatusForm(initial={"_selected_action": queryset.values_list("id", flat=True)})
        return render(
            request,
            "admin/update_status.html",
            context={"form": form},
        )


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

    @admin.display(
        description="object",
        ordering="object_repr",
    )
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


@admin.register(MemberUpdate)
class MemberUpdateAdmin(SearchAdmin, admin.ModelAdmin):
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
    search_fields = [
        "user__name",
        "first_name",
        "last_name",
        "user__preferred_name",
    ]
