from django.contrib import admin
from chapters.models import Chapter, ChapterCurricula
from notes.admin import ChapterNoteInline, ChapterNote
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

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for instance in instances:
            if isinstance(instance, ChapterNote):
                user = request.user
                if not change or not hasattr(instance, "created_by"):
                    instance.created_by = user
                instance.modified_by = user
                instance.save()
        formset.save()


admin.site.register(Chapter, ChapterAdmin)
