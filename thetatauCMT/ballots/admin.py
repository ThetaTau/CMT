from django.contrib import admin
from .models import Ballot, BallotComplete


class BallotCompleteAdmin(admin.ModelAdmin):
    list_display = ('user', 'ballot', 'motion', 'role')
    list_filter = ['motion', 'ballot']
    ordering = ['created',]


class BallotCompleteInline(admin.TabularInline):
    model = BallotComplete
    fields = ['user', 'user__chapter', 'motion',]
    show_change_link = False
    ordering = ['user__chapter']
    extra = 0


class BallotAdmin(admin.ModelAdmin):
    inlines = [BallotCompleteInline]
    list_display = ('name', 'type', 'due_date', 'voters')
    list_filter = ['type', 'voters']
    ordering = ['created',]


admin.site.register(Ballot, BallotAdmin)
admin.site.register(BallotComplete, BallotCompleteAdmin)
