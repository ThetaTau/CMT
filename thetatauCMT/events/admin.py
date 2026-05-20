from django.contrib import admin

from .models import Event

# Register your models here.


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "date", "chapter", "type", "description")
    list_filter = ["chapter", "type"]
    ordering = [
        "date",
    ]
    readonly_fields = (
        "created_by",
        "modified_by",
    )
