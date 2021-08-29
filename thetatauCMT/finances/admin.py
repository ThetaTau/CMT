from django.contrib import admin
from .models import Invoice


class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "due_date",
        "chapter",
        "total",
    )
    list_filter = [
        "chapter",
    ]
    ordering = [
        "-due_date",
    ]


admin.site.register(Invoice, InvoiceAdmin)
