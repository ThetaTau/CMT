from django.contrib import admin
from chapters.models import Chapter, ChapterCurricula
from notes.admin import ChapterNoteInline
from .views import DuesSyncMixin


class ChapterCurriculaInline(admin.TabularInline):
    model = ChapterCurricula
    fields = ["major", "approved"]
    ordering = ["-approved", "major"]
    show_change_link = True


class ChapterAdmin(admin.ModelAdmin, DuesSyncMixin):
    actions = ["sync_dues", "reminder_dues"]
    list_per_page = 200
    inlines = [ChapterNoteInline, ChapterCurriculaInline]
    list_filter = [
        "region",
        "active",
        "candidate_chapter",
        "school_type",
        "recognition",
    ]
    search_fields = ["name", "school"]
    ordering = ["name"]


admin.site.register(Chapter, ChapterAdmin)
