from django.contrib import admin

from .models import BigLittle, PendingPairing


class CurrentListFilter(admin.SimpleListFilter):
    title = "current or former"
    parameter_name = "current"

    def lookups(self, request, model_admin):
        return (("yes", "Current"), ("no", "Former"))

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.current()
        if self.value() == "no":
            return queryset.former()
        return queryset


@admin.register(BigLittle)
class BigLittleAdmin(admin.ModelAdmin):
    list_display = ("little", "big", "chapter", "source", "created", "ended")
    list_filter = (CurrentListFilter, "source")
    list_select_related = ("little", "big", "chapter")
    search_fields = ("little__name", "big__name", "chapter__name")
    raw_id_fields = ("big", "little", "chapter", "created_by", "ended_by")
    readonly_fields = ("created", "modified")

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PendingPairing)
class PendingPairingAdmin(admin.ModelAdmin):
    list_display = ("chapter", "line", "little_text", "big_text", "status", "created", "resolved_at")
    list_filter = ("status",)
    list_select_related = ("chapter",)
    search_fields = ("little_text", "big_text", "chapter__name")
    raw_id_fields = ("chapter", "little", "big", "uploaded_by", "resolved_by")
    readonly_fields = ("fingerprint", "created", "modified")
