from django.contrib import admin

from .models import Config


@admin.register(Config)
class ConfigAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "description", "created", "modified")
    list_filter = ["created", "modified"]
    search_fields = ["key", "value"]
    ordering = [
        "-created",
    ]
