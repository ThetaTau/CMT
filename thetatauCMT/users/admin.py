from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry, DELETION
from django.utils.html import escape
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib.auth.models import Permission
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from import_export.admin import ImportExportActionModelAdmin
from address.widgets import AddressWidget
from .models import (
    User,
    UserRoleChange,
    UserStatusChange,
    UserOrgParticipate,
    UserSemesterGPA,
    UserSemesterServiceHours,
    UserAlter,
    ChapterCurricula,
)
from .resources import UserRoleChangeResource
from .views import ExportActiveMixin
from forms.models import Depledge, Initiation, StatusChange
from core.admin import user_chapter


admin.site.register(Permission)


class UserStatusChangeAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "status", "created", user_chapter)
    list_filter = ["status", "created", "user__chapter"]
    ordering = [
        "-created",
    ]
    search_fields = ["user__name"]


admin.site.register(UserStatusChange, UserStatusChangeAdmin)


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


class MyUserCreationForm(UserCreationForm):

    error_message = UserCreationForm.error_messages.update(
        {"duplicate_username": "This username has already been taken."}
    )

    class Meta(UserCreationForm.Meta):
        model = User

    def clean_username(self):
        username = self.cleaned_data["username"]
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            return username
        raise forms.ValidationError(self.error_messages["duplicate_username"])


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


class UserAlterInline(admin.StackedInline):
    model = UserAlter
    fields = ["chapter", "role"]
    show_change_link = True
    extra = 0


@admin.register(User)
class MyUserAdmin(AuthUserAdmin, ExportActiveMixin):
    actions = ["export_chapter_actives"]
    inlines = [
        UserAlterInline,
        StatusInline,
        RoleInline,
        InitiationInline,
        StatusChangeInline,
        DepledgeInline,
    ]
    form = MyUserChangeForm
    add_form = MyUserCreationForm
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
                    "birth_date",
                    "email",
                    "email_school",
                    "address",
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
        if db_field.name == "address":
            kwargs["widget"] = AddressWidget()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(LogEntry)
class LogEntryAdmin(admin.ModelAdmin):
    date_hierarchy = "action_time"

    list_filter = ["user", "content_type", "action_flag"]

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
