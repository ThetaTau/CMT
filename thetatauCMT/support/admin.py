from django.contrib import admin

from core.models import CSS_ROLE

from .models import ChapterSupportAssignment, SupportDigestEntry


class AssignmentStateFilter(admin.SimpleListFilter):
    title = "state"
    parameter_name = "state"

    def lookups(self, request, model_admin):
        return (("current", "Current"), ("upcoming", "Not started yet"), ("ended", "Ended"))

    def queryset(self, request, queryset):
        if self.value() == "current":
            return queryset.current()
        if self.value() == "upcoming":
            return queryset.upcoming()
        if self.value() == "ended":
            return queryset.ended()
        return queryset


@admin.register(ChapterSupportAssignment)
class ChapterSupportAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "chapter", "region", "start", "end", "created_by")
    list_filter = (AssignmentStateFilter, "chapter__region")
    list_select_related = ("user", "chapter", "chapter__region", "created_by")
    search_fields = ("user__name", "user__email", "chapter__name")
    raw_id_fields = ("user",)
    fields = ("user", "chapter", "start", "end", "notes", "created_by", "ended_by", "created", "modified")
    readonly_fields = ("created_by", "ended_by", "created", "modified")

    @admin.display(description="Region", ordering="chapter__region__name")
    def region(self, obj):
        return obj.chapter.region

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        changed = form.changed_data if form is not None else ["end"]
        if obj.end is None:
            obj.ended_by = None
        elif not change or "end" in changed:
            obj.ended_by = request.user
        super().save_model(request, obj, form, change)


class SupportAssignmentInline(admin.TabularInline):
    """Read-only list on a CSS's User admin page.

    Assignments are made on their own admin page (or the CSS page in CSSWI-5), which
    records who made them. Members who never held the role do not see the section.
    """

    model = ChapterSupportAssignment
    fk_name = "user"
    fields = ("chapter", "start", "end", "created_by")
    readonly_fields = fields
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name_plural = "Chapter Support Specialist assignments"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        if obj is None or not super().has_view_permission(request, obj):
            return False
        return CSS_ROLE in (obj.current_roles or []) or obj.support_assignments.exists()

    def has_change_permission(self, request, obj=None):
        return self.has_view_permission(request, obj)


@admin.register(SupportDigestEntry)
class SupportDigestEntryAdmin(admin.ModelAdmin):
    list_display = ("created", "user", "chapter", "kind", "subject", "realtime", "daily_sent_at", "monthly_sent_at")
    list_filter = ("kind", "realtime")
    list_select_related = ("user", "chapter")
    search_fields = ("user__name", "user__email", "chapter__name", "subject")
    date_hierarchy = "created"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
