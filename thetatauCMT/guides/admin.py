from django.contrib import admin

from .models import Feature, FeatureArea, RoleGuide, RoleGuideStep, UserAcknowledgement


class FeatureInline(admin.TabularInline):
    model = Feature
    fields = [
        "order",
        "key",
        "name",
        "short_description",
        "url_name",
        "audience",
        "is_highlighted",
        "is_active",
    ]
    show_change_link = True
    ordering = ["order", "name"]
    extra = 1


@admin.register(FeatureArea)
class FeatureAreaAdmin(admin.ModelAdmin):
    inlines = [FeatureInline]
    list_display = (
        "name",
        "key",
        "order",
        "audience",
        "feature_flag",
        "is_active",
    )
    list_filter = ["audience", "feature_flag", "is_active"]
    search_fields = ["name", "key", "description"]
    ordering = [
        "order",
        "name",
    ]


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "key",
        "area",
        "order",
        "audience",
        "feature_flag",
        "is_highlighted",
        "is_active",
    )
    list_filter = ["area", "audience", "feature_flag", "is_highlighted", "is_active"]
    search_fields = ["name", "key", "short_description"]
    ordering = [
        "area__order",
        "order",
        "name",
    ]


class RoleGuideStepInline(admin.TabularInline):
    model = RoleGuideStep
    fields = [
        "order",
        "title",
        "cadence",
        "feature",
        "task",
    ]
    show_change_link = True
    ordering = ["order", "id"]
    extra = 1
    autocomplete_fields = ["feature"]


@admin.register(RoleGuide)
class RoleGuideAdmin(admin.ModelAdmin):
    inlines = [RoleGuideStepInline]
    list_display = ("title", "role", "slug", "order", "is_active")
    list_filter = ["is_active"]
    search_fields = ["title", "role", "summary"]
    readonly_fields = ["slug"]
    ordering = ["order", "title"]


@admin.register(RoleGuideStep)
class RoleGuideStepAdmin(admin.ModelAdmin):
    list_display = ("title", "guide", "order", "cadence", "feature", "task")
    list_filter = ["guide", "cadence"]
    search_fields = ["title", "body"]
    ordering = ["guide__order", "order", "id"]


@admin.register(UserAcknowledgement)
class UserAcknowledgementAdmin(admin.ModelAdmin):
    """Read-only: rows are written by the acknowledge endpoint, never by hand.

    Deleting a row here re-shows the item to that user, which is the supported
    way to give someone a second look at an announcement.
    """

    list_display = ("user", "content_type", "object_id", "source", "acknowledged_at")
    list_filter = ["content_type", "source", "acknowledged_at"]
    search_fields = ["user__username", "user__name"]
    readonly_fields = ("user", "content_type", "object_id", "source", "acknowledged_at")
    list_select_related = ("user", "content_type")

    def has_add_permission(self, request):
        return False
