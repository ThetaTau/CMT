# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Transaction
from regions.models import Region


class TransactionListFilter(django_filters.FilterSet):
    due_date = DateRangeFilter(field_name='due_date')

    class Meta:
        model = Transaction
        fields = ['paid', 'due_date', 'type', 'estimate', ]
        order_by = ['-due_date']


class ChapterBalanceListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        label="Region",
        choices=Region.region_choices(),
        method='filter_region'
    )

    class Meta:
        model = Transaction
        fields = ['region', ]

    def filter_region(self, queryset, field_name, value):
        if value == 'national':
            return queryset
        elif value == 'colony':
            queryset = queryset.filter(colony=True)
        else:
            queryset = queryset.filter(region_slug=value)
        return queryset
