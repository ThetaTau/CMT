from django.contrib import admin

from .models import PositionOverride, ReportTemplate, TemplatePrompt, position_type_for_key


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
