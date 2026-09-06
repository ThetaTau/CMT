from django.contrib import admin

from .models import (
    PositionOverride,
    ReportAnswer,
    ReportAttachment,
    ReportTemplate,
    TemplatePrompt,
    TransitionReport,
    position_type_for_key,
)


@admin.register(PositionOverride)
class PositionOverrideAdmin(admin.ModelAdmin):
    list_display = ("position_key", "status", "position_type")
    list_filter = ("status",)
    search_fields = ("position_key",)
    ordering = ("position_key",)

    @admin.display(description="Position type")
    def position_type(self, obj):
        position_type = position_type_for_key(obj.position_key)
        return position_type.value[1] if position_type else "—"


class TemplatePromptInline(admin.TabularInline):
    model = TemplatePrompt
    extra = 0
    fields = (
        "order",
        "prompt_key",
        "label",
        "field_type",
        "is_required",
        "min_chars",
        "max_chars",
        "tag",
        "help_text",
    )
    ordering = ("order",)


@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "position_type", "position_key", "version", "is_active")
    list_filter = ("position_type", "is_active")
    search_fields = ("name", "position_key")
    ordering = ("position_type", "position_key")
    inlines = [TemplatePromptInline]


class ReportAnswerInline(admin.TabularInline):
    model = ReportAnswer
    extra = 0
    fields = ("prompt_key", "prompt_label_snapshot", "value")
    readonly_fields = ("prompt_key", "prompt_label_snapshot", "value")
    can_delete = False


class ReportAttachmentInline(admin.TabularInline):
    model = ReportAttachment
    extra = 0
    fields = ("file", "description", "uploaded_by", "uploaded_at")
    readonly_fields = ("uploaded_by", "uploaded_at")


@admin.register(TransitionReport)
class TransitionReportAdmin(admin.ModelAdmin):
    """Read-oriented -- national committee oversight, not day-to-day editing.

    Officers compose/submit through the front-end view (TRWI-5); this exists
    for the committee to spot-check content quality (Pre-Launch Checklist
    F16) and for support to look up a specific report.
    """

    list_display = ("position_key", "chapter", "author", "status", "submitted_at")
    list_filter = ("position_type", "status")
    search_fields = ("position_key", "chapter__name", "author__name")
    ordering = ("-created",)
    inlines = [ReportAnswerInline, ReportAttachmentInline]
