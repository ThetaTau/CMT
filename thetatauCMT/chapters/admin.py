from django.contrib import admin
from chapters.models import Chapter, ChapterCurricula


class ChapterCurriculaInline(admin.TabularInline):
    model = ChapterCurricula
    fields = ["major"]
    ordering = ["major"]
    show_change_link = True


class ChapterAdmin(admin.ModelAdmin):
    inlines = [ChapterCurriculaInline]
    list_filter = ["region", "active", "colony", "school_type", "recognition"]
    search_fields = ["name", "school"]
    ordering = ["name"]


admin.site.register(Chapter, ChapterAdmin)
