from django.contrib import admin
from .models import Ballot
# Register your models here.


class BallotAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'chapter', 'type', 'description')
    list_filter = ['chapter', 'type']
    ordering = ['date',]


admin.site.register(Ballot, BallotAdmin)
