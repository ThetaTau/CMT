# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Audit


class AuditListFilter(django_filters.FilterSet):
    modified = DateRangeFilter()

    class Meta:
        model = Audit
        fields = ['modified', 'user__chapter', 'user__chapter__region',
                  'debit_card',]
        order_by = ['user__chapter']
