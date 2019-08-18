# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Transaction


class TransactionListFilter(django_filters.FilterSet):
    due_date = DateRangeFilter(field_name='due_date')

    class Meta:
        model = Transaction
        fields = ['paid', 'due_date', 'type',]
        order_by = ['-due_date']
