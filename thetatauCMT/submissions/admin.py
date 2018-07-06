from django.contrib import admin
from .models import Submission
# Register your models here.

class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'type', 'file')
    list_filter = ['chapter', 'type']
    ordering = ['date',]

admin.site.register(Submission, SubmissionAdmin)
