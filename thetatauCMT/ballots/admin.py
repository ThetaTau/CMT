from django.contrib import admin

from .models import Ballot, BallotComplete


@admin.register(BallotComplete)
class BallotCompleteAdmin(admin.ModelAdmin):
    """Who returned a ballot, never how they voted.

    ``motion`` is excluded everywhere in the admin: a ballot is secret, only the
    voter sees their own vote, and only the Grand Regent and Grand Scribe see
    the aggregate counts. Votes are cast through the site, so they cannot be
    added here either.
    """

    raw_id_fields = ["user"]
    list_display = ("user", "ballot", "role", "authority", "created")
    list_filter = ["ballot", "role", "authority"]
    search_fields = ["user__name", "user__username", "ballot__name"]
    exclude = ["motion"]
    ordering = [
        "created",
    ]

    def has_add_permission(self, request):
        return False


class BallotCompleteInline(admin.TabularInline):
    model = BallotComplete
    raw_id_fields = ["user"]
    fields = [
        "user",
        "role",
        "authority",
    ]
    show_change_link = False
    can_delete = False
    extra = 0

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ballot)
class BallotAdmin(admin.ModelAdmin):
    inlines = [BallotCompleteInline]
    list_display = ("name", "type", "due_date", "voters")
    list_filter = ["type", "voters"]
    ordering = [
        "created",
    ]
