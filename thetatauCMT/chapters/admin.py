from django.contrib import admin
from .models import Chapter, ChapterCurricula


class ChapterCurriculaInline(admin.TabularInline):
    model = ChapterCurricula
    fields = ['major']
    show_change_link = True
    ordering = ['major']
    extra = 1


class ChapterAdmin(admin.ModelAdmin):
    inlines = [ChapterCurriculaInline,]
    list_display = ('name', 'region', 'school')
    list_filter = ['region']
    ordering = ['name',]


admin.site.register(Chapter, ChapterAdmin)
