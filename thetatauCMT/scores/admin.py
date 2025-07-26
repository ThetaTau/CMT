from django.contrib import admin
from .models import ScoreType, ScoreChapter

# Register your models here.


@admin.register(ScoreType)
class ScoreTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "section", "type")
    list_filter = ["section", "type"]
    search_fields = ["name"]


@admin.register(ScoreChapter)
class ScoreChapterAdmin(admin.ModelAdmin):
    list_display = ("chapter", "score", "type", "year", "term")
    list_filter = ["year", "term", "chapter", "type"]
    search_fields = ["chapter__name", "year", "term", "type"]
