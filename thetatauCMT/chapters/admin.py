from django.contrib import admin
from django.conf import settings
from .models import Chapter
# Register your models here.


class MemberInline(admin.TabularInline):
    # model = settings.AUTH_USER_MODEL
    fields = ['name', 'user_id']
    readonly_fields = ('name', 'user_id')
    can_delete = False
    ordering = ['name']
    show_change_link = True

    def has_add_permission(self, _):
        return False


class ChapterAdmin(admin.ModelAdmin):
    # inlines = [MemberInline]
    list_display = ('name', 'region', 'school')
    list_filter = ['region']
    ordering = ['name',]


admin.site.register(Chapter, ChapterAdmin)
