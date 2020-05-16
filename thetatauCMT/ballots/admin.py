from django.contrib import admin
from .models import Ballot, BallotComplete


class BallotCompleteAdmin(admin.ModelAdmin):
    raw_id_fields = ["user"]
    list_display = ("user", "ballot", "motion", "role")
    list_filter = ["motion", "ballot"]
    ordering = [
        "created",
    ]


class BallotCompleteInline(admin.TabularInline):
    model = BallotComplete
    raw_id_fields = ["user"]
    fields = [
        "user",
        "motion",
    ]
    show_change_link = False
    can_delete = False
    extra = 0

    def has_change_permission(self, request, obj=None):
        return False


class BallotAdmin(admin.ModelAdmin):
    inlines = [BallotCompleteInline]
    list_display = ("name", "type", "due_date", "voters")
    list_filter = ["type", "voters"]
    ordering = [
        "created",
    ]


admin.site.register(Ballot, BallotAdmin)
admin.site.register(BallotComplete, BallotCompleteAdmin)
