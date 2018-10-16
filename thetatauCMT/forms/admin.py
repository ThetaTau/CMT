from django.contrib import admin
from .models import Badge, Guard, Initiation, Depledge, StatusChange
from core.admin import user_chapter


admin.site.register(Badge)
admin.site.register(Guard)


class InitiationAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'date', 'created', user_chapter)
    list_filter = ['date', 'created', 'user__chapter']
    ordering = ['-created',]
    search_fields = ['user__username', 'user__name']



admin.site.register(Initiation, InitiationAdmin)


class DepledgeAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'reason', 'date', 'created', user_chapter)
    list_filter = ['reason', 'date', 'created', 'user__chapter']
    ordering = ['-created',]
    search_fields = ['user__username', 'user__name']


admin.site.register(Depledge, DepledgeAdmin)


class StatusChangeAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'reason', 'date_start', 'date_end', 'created', user_chapter)
    list_filter = ['reason', 'date_start', 'date_end', 'user__chapter']
    ordering = ['-created',]
    search_fields = ['user__username', 'user__name']


admin.site.register(StatusChange, StatusChangeAdmin)
