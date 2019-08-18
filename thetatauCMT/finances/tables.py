import django_tables2 as tables
from .models import Transaction


class TransactionTable(tables.Table):
    class Meta:
        model = Transaction
        fields = ('type', 'due_date', 'description', 'paid', 'total',
                  )
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no transactions matching the search criteria..."
