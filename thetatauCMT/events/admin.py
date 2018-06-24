from django.contrib import admin
from .models import Event
# Register your models here.


class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'chapter', 'type', 'description')
    list_filter = ['chapter', 'type']
    ordering = ['date',]


admin.site.register(Event, EventAdmin)
