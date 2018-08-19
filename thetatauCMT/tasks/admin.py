from django.contrib import admin
from .models import Task, TaskDate, TaskChapter


class TaskDateInline(admin.TabularInline):
    model = TaskDate
    fields = ['school_type', 'date']
    show_change_link = True
    ordering = ['date']
    extra = 1


class TaskAdmin(admin.ModelAdmin):
    inlines = [TaskDateInline]
    list_display = ('name', 'owner', 'type', 'submission_type')
    list_filter = ['owner', 'type']
    ordering = ['name',]


class TaskChapterAdmin(admin.ModelAdmin):
    list_display = ('task', 'chapter', 'date', 'submission_type')
    list_filter = ['chapter', 'date']
    ordering = ['date',]


admin.site.register(Task, TaskAdmin)
admin.site.register(TaskChapter, TaskChapterAdmin)
admin.site.register(TaskDate)
