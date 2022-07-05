from django.contrib import admin
from .models import Objective, Action


class ActionInline(admin.TabularInline):
    model = Action
    raw_id_fields = ["owner"]
    fields = ["owner", "date", "complete", "description"]
    show_change_link = True
    ordering = ["-date"]
    extra = 1


class ObjectiveAdmin(admin.ModelAdmin):
    inlines = [ActionInline]
    raw_id_fields = ["owner", "user"]
    list_display = (
        "title",
        "complete",
        "restricted_ec",
        "restricted_co",
        "date",
        "owner",
        "user",
        "chapter",
    )
    list_filter = [
        "complete",
        "restricted_ec",
        "restricted_co",
        "date",
        "chapter",
    ]
    ordering = [
        "-date",
    ]


admin.site.register(Objective, ObjectiveAdmin)
