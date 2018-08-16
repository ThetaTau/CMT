from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as AuthUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from .models import User, UserRoleChange, UserStatusChange, UserOrgParticipate,\
    UserSemesterGPA, UserSemesterServiceHours


admin.site.register(UserStatusChange)

class UserOrgParticipateAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'org_name', 'type', 'officer', 'start', 'end')
    list_filter = ['start', 'end', 'officer', 'type']
    ordering = ['-start',]


admin.site.register(UserOrgParticipate, UserOrgParticipateAdmin)


class UserSemesterGPAAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'gpa', 'year', 'term')
    list_filter = ['year', 'term']
    ordering = ['-year',]


admin.site.register(UserSemesterGPA, UserSemesterGPAAdmin)


class UserSemesterServiceHoursAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'service_hours', 'year', 'term')
    list_filter = ['year', 'term']
    ordering = ['-year',]


admin.site.register(UserSemesterServiceHours,
                    UserSemesterServiceHoursAdmin)


class MemberInline(admin.TabularInline):
    model = User
    fields = ['name', 'user_id']
    readonly_fields = ('name', 'user_id')
    can_delete = False
    ordering = ['name']
    show_change_link = True

    def has_add_permission(self, _):
        return False


class UserRoleChangeAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'start', 'end')
    list_filter = ['start', 'end', 'role']
    ordering = ['-end',]


admin.site.register(UserRoleChange, UserRoleChangeAdmin)


class MyUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User


class MyUserCreationForm(UserCreationForm):

    error_message = UserCreationForm.error_messages.update({
        'duplicate_username': 'This username has already been taken.'
    })

    class Meta(UserCreationForm.Meta):
        model = User

    def clean_username(self):
        username = self.cleaned_data["username"]
        try:
            User.objects.get(username=username)
        except User.DoesNotExist:
            return username
        raise forms.ValidationError(self.error_messages['duplicate_username'])


@admin.register(User)
class MyUserAdmin(AuthUserAdmin):
    form = MyUserChangeForm
    add_form = MyUserCreationForm
    fieldsets = (
            ('User Profile', {'fields': ('name', 'chapter')}),
    ) + AuthUserAdmin.fieldsets
    list_display = ('username', 'name', 'last_login', 'user_id')
    list_filter = ('is_superuser', 'last_login', 'groups')
