from django.contrib import admin

from .models import PositionOverride, position_type_for_key


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
