from django.contrib import admin
from .models import Transaction


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('type', 'due_date', 'chapter', 'paid', 'total',)
    list_filter = ['chapter', 'type', 'paid']
    ordering = ['-due_date', ]


admin.site.register(Transaction, TransactionAdmin)
