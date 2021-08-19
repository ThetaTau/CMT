from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from django.utils.html import escape
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib.auth.models import Permission
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.forms import UserChangeForm
from import_export.admin import ImportExportActionModelAdmin
from report_builder.admin import Report
from .models import (
    User,
    UserRoleChange,
    UserStatusChange,
    UserOrgParticipate,
    UserSemesterGPA,
    UserSemesterServiceHours,
    UserAlter,
    ChapterCurricula,
    UserDemographic,
)
from .resources import UserRoleChangeResource
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
from core.admin import user_chapter, ReportAdminSync
from notes.admin import UserNoteInline, UserNote


admin.site.register(Permission)
admin.site.unregister(Report)
admin.site.register(Report, ReportAdminSync)


class UserStatusChangeAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "status", "created", user_chapter)
    list_filter = ["status", "created", "user__chapter"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__name"]


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

    def has_add_permission(self, _):
        return False


class UserRoleChangeAdmin(ImportExportActionModelAdmin):
    list_display = ("user", "role", "start", "end", "created", user_chapter)
    list_filter = ["start", "end", "role", "created", "user__chapter"]
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
    fields = ["role", "start", "end"]
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
class MyUserAdmin(AuthUserAdmin, ExportActiveMixin):
    actions = ["export_chapter_actives"]
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
    )
    list_filter = ("is_superuser", "last_login", "groups", "chapter")
    search_fields = ("user_id", "badge_number") + AuthUserAdmin.search_fields

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "major":
            try:
                user_id = request.resolver_match.kwargs.get("object_id")
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

    def has_add_permission(self, request):
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
