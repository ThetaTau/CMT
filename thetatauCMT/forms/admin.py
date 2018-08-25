from django.contrib import admin
from .models import Badge, Guard, Initiation, Depledge, StatusChange
# Register your models here.


admin.site.register(Badge)
admin.site.register(Guard)


class InitiationAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'date', 'created')
    list_filter = ['date', 'created']
    ordering = ['user',]
    search_fields = ['user__username', 'user__name']


admin.site.register(Initiation, InitiationAdmin)


class DepledgeAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'reason', 'date', 'created')
    list_filter = ['reason', 'date', 'created']
    ordering = ['user',]
    search_fields = ['user__username', 'user__name']


admin.site.register(Depledge, DepledgeAdmin)


class StatusChangeAdmin(admin.ModelAdmin):
    raw_id_fields = ['user']
    list_display = ('user', 'reason', 'date_start', 'date_end', 'created')
    list_filter = ['reason', 'date_start', 'date_end']
    ordering = ['user',]
    search_fields = ['user__username', 'user__name']


admin.site.register(StatusChange, StatusChangeAdmin)
