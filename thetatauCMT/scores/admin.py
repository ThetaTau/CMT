from django.contrib import admin
from .models import ScoreType

# Register your models here.


class ScoreTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "type")
    list_filter = ["section", "type"]
    search_fields = ["name"]


admin.site.register(ScoreType, ScoreTypeAdmin)
