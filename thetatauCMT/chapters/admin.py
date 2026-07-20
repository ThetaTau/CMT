from django import forms
from django.contrib import admin

from core.forms import ComponentAddressField
from core.signals import SignalWatchMixin
from thetatauCMT.chapters.models import Chapter, ChapterCurricula
from thetatauCMT.notes.admin import ChapterNote, ChapterNoteInline

from .views import DuesSyncMixin


class ChapterCurriculaInline(admin.TabularInline):
    model = ChapterCurricula
    fields = ["major", "approved"]
    ordering = ["-approved", "major"]
    show_change_link = True


class ChapterAdminForm(forms.ModelForm):
    address = ComponentAddressField(required=False)

    class Meta:
        model = Chapter
        fields = "__all__"


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin, DuesSyncMixin, SignalWatchMixin):
    object_type = "chapter"
    form = ChapterAdminForm
    actions = [
        "sync_dues",
        "reminder_dues",
        "watch_notification_add",
        "watch_notification_remove",
    ]
    list_per_page = 200
    inlines = [ChapterNoteInline, ChapterCurriculaInline]
    list_display = ["name", "school", "region", "active", "founding_date"]
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
