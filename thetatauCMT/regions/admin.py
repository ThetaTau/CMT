from django.contrib import admin
from .models import Region
from chapters.models import Chapter


class ChapterInline(admin.TabularInline):
    model = Chapter
    fields = ["name", "school"]
    readonly_fields = ("name", "school")
    can_delete = False
    ordering = ["name"]
    show_change_link = True

    def has_add_permission(self, _, obj=None):
        return False


class RegionTypeAdmin(admin.ModelAdmin):
    inlines = [ChapterInline]
    raw_id_fields = ["directors"]
    list_filter = ["name"]
    search_fields = ["name"]
    ordering = ["name"]


admin.site.register(Region, RegionTypeAdmin)
