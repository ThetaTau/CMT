from django.contrib import admin

from .models import (
    AwardCycle,
    AwardDigestRun,
    AwardGrant,
    AwardImportMatchQueueItem,
    AwardType,
    EligibilityRule,
    GrantArtifact,
    GrantAudit,
    OfficerBadge,
)


class EligibilityRuleInline(admin.StackedInline):
    model = EligibilityRule
    extra = 0
    filter_horizontal = ("chapters", "regions")
    fields = ("rule_type", "member_status", "chapters", "regions", "hook_key", "params")


@admin.register(AwardType)
class AwardTypeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "level",
        "category",
        "grant_method",
        "recurrence",
        "single_winner",
        "allow_multiple_winners",
        "allow_multiple_nominations",
        "points",
        "is_active",
        "auto_generate_certificate",
    )
    list_filter = (
        "level",
        "grant_method",
        "recurrence",
        "is_active",
        "single_winner",
        "allow_multiple_winners",
        "allow_multiple_nominations",
    )
    search_fields = ("name", "description", "category", "eligibility")
    list_editable = ("is_active",)
    readonly_fields = ("created", "modified")
    fieldsets = (
        (None, {"fields": ("name", "description", "eligibility", "category", "level", "badge_image", "points")}),
        ("Grant configuration", {"fields": ("grant_method", "nominator_scope", "auto_generate_certificate")}),
        (
            "Cycle rules",
            {
                "fields": (
                    "recurrence",
                    "single_winner",
                    "allow_multiple_winners",
                    "allow_multiple_nominations",
                )
            },
        ),
        ("Status", {"fields": ("is_active", "created", "modified")}),
    )
    inlines = [EligibilityRuleInline]


@admin.register(EligibilityRule)
class EligibilityRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "award_type", "rule_type", "member_status", "hook_key")
    list_filter = ("rule_type", "member_status")
    search_fields = ("award_type__name", "hook_key")
    raw_id_fields = ("award_type",)
    filter_horizontal = ("chapters", "regions")


@admin.register(AwardCycle)
class AwardCycleAdmin(admin.ModelAdmin):
    list_display = ("name", "period_type", "start_date", "end_date", "event", "is_current_display")
    list_filter = ("period_type",)
    search_fields = ("name",)
    raw_id_fields = ("event",)
    readonly_fields = ("created", "modified")

    @admin.display(boolean=True, description="Current")
    def is_current_display(self, obj):
        return obj.is_current


class GrantAuditInline(admin.TabularInline):
    model = GrantAudit
    extra = 0
    can_delete = False
    ordering = ("timestamp",)
    readonly_fields = ("action", "actor", "timestamp", "detail")

    def has_add_permission(self, request, obj=None):
        return False


class GrantArtifactInline(admin.TabularInline):
    model = GrantArtifact
    extra = 0
    fields = ("artifact_type", "file", "generated_at", "uploaded_at", "created_by")
    readonly_fields = ("generated_at", "uploaded_at")
    raw_id_fields = ("created_by",)


@admin.register(AwardGrant)
class AwardGrantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "award_type",
        "cycle",
        "recipient_col",
        "recipient_kind",
        "status",
        "source",
        "effective_date",
        "granted_by",
        "granted_at",
    )
    list_filter = ("status", "source", "award_type__level", "award_type", "cycle")
    search_fields = (
        "award_type__name",
        "cycle__name",
        "recipient_member__name",
        "recipient_chapter__name",
        "recipient_region__name",
        "reason",
    )
    raw_id_fields = (
        "award_type",
        "cycle",
        "recipient_member",
        "recipient_chapter",
        "recipient_region",
        "granted_by",
        "revoked_by",
    )
    readonly_fields = ("granted_at", "created", "modified")
    date_hierarchy = "effective_date"
    inlines = [GrantArtifactInline, GrantAuditInline]

    @admin.display(description="Recipient")
    def recipient_col(self, obj):
        return obj.recipient_display


@admin.register(GrantAudit)
class GrantAuditAdmin(admin.ModelAdmin):
    list_display = ("id", "grant", "action", "actor", "timestamp")
    list_filter = ("action", "timestamp")
    search_fields = ("grant__id", "actor__name")
    readonly_fields = ("grant", "action", "actor", "timestamp", "detail")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(GrantArtifact)
class GrantArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "grant", "artifact_type", "created_by", "generated_at", "uploaded_at")
    list_filter = ("artifact_type",)
    search_fields = ("grant__id",)
    raw_id_fields = ("grant", "created_by")
    readonly_fields = ("generated_at", "uploaded_at")


@admin.register(AwardDigestRun)
class AwardDigestRunAdmin(admin.ModelAdmin):
    list_display = ("id", "period_start", "period_end", "grant_count", "sent_at", "sent_by")
    list_filter = ("period_start",)
    readonly_fields = ("period_start", "period_end", "grant_count", "sent_at", "sent_by")


@admin.register(OfficerBadge)
class OfficerBadgeAdmin(admin.ModelAdmin):
    list_display = ("role", "short_label", "icon_class", "is_active")
    list_filter = ("is_active",)
    search_fields = ("role", "short_label")
    list_editable = ("is_active",)


@admin.register(AwardImportMatchQueueItem)
class AwardImportMatchQueueItemAdmin(admin.ModelAdmin):
    list_display = ("id", "raw_recipient", "recipient_kind", "award_type", "cycle", "best_score", "status", "created")
    list_filter = ("status", "recipient_kind")
    search_fields = ("raw_recipient", "raw_award", "raw_cycle")
    raw_id_fields = (
        "award_type",
        "cycle",
        "resolved_recipient_member",
        "resolved_recipient_chapter",
        "resolved_recipient_region",
        "resolved_grant",
        "resolved_by",
        "uploaded_by",
    )
    readonly_fields = ("upload_id", "fingerprint", "raw_row", "candidate_matches", "best_score")
