from django.contrib import admin

from .models import Nomination, NominationContact


class NominationContactInline(admin.TabularInline):
    """Read-only inline log of every contact/communication with the nominee (#12)."""

    model = NominationContact
    extra = 0
    can_delete = False
    ordering = ("-sent_at",)
    readonly_fields = ("kind", "subject", "recipient", "notes", "sent_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Nomination)
class NominationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "nominee_col",
        "nominator",
        "level_col",
        "current_step",
        "consent_status",
        "appointed",
        "not_interested",
        "created",
        "finished",
    )
    list_filter = (
        "consent_status",
        "not_interested",
        "appointed",
        "finished",
    )
    search_fields = (
        "nominee_name",
        "nominee_email",
        "nominee__name",
        "nominator__name",
        "reason",
    )
    raw_id_fields = ("nominee", "nominator")
    readonly_fields = ("consent_token", "created", "finished", "current_step")
    inlines = [NominationContactInline]

    @admin.display(description="Nominee")
    def nominee_col(self, obj):
        return obj.nominee_display

    @admin.display(description="Level(s)")
    def level_col(self, obj):
        return obj.get_level_display()


@admin.register(NominationContact)
class NominationContactAdmin(admin.ModelAdmin):
    list_display = ("id", "nomination", "kind", "recipient", "subject", "sent_at")
    list_filter = ("kind", "sent_at")
    search_fields = ("recipient", "subject", "notes", "nomination__nominee__name")
    readonly_fields = ("nomination", "kind", "subject", "recipient", "notes", "sent_at")
