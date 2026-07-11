from django.contrib import admin

from .models import UserContactSyncToken


@admin.register(UserContactSyncToken)
class UserContactSyncTokenAdmin(admin.ModelAdmin):
    list_display = ("user", "provider", "account_email", "last_synced_at", "last_sync_count", "modified")
    list_filter = ("provider",)
    search_fields = ("user__email", "user__name", "account_email")
    autocomplete_fields = ("user",)
    readonly_fields = (
        "created",
        "modified",
        "access_token_encrypted",
        "refresh_token_encrypted",
        "scope",
        "token_type",
        "expires_at",
        "last_synced_at",
        "last_sync_count",
        "last_error",
    )
