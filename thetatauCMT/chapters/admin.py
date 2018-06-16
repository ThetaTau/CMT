from django.contrib import admin
from .models import Chapter
# Register your models here.


class ChapterAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'school')
    list_filter = ['region']
    ordering = ['name',]


admin.site.register(Chapter, ChapterAdmin)
