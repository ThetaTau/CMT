# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Audit, PledgeProgram
from regions.models import Region


class AuditListFilter(django_filters.FilterSet):
    modified = DateRangeFilter()

    class Meta:
        model = Audit
        fields = ['modified', 'user__chapter', 'user__chapter__region',
                  'debit_card',]
        order_by = ['user__chapter']


class CompleteListFilter(django_filters.FilterSet):
    complete = django_filters.ChoiceFilter(
        label='Complete',
        method='filter_complete',
        choices=(
            ('1', 'Complete'),
            ('0', 'Incomplete'),
            ('', 'All'),
        )
    )
    region = django_filters.ChoiceFilter(
        label="Region",
        choices=Region.region_choices(),
        method='filter_region'
    )

    class Meta:
        model = PledgeProgram  # This is needed to automatically make year/term
        fields = ['region', 'year', 'term', 'complete']
        order_by = ['chapter']

    def filter_complete(self, queryset, field_name, value):
        return queryset

    def filter_region(self, queryset, field_name, value):
        if value == 'national':
            return queryset
        elif value == 'colony':
            queryset = queryset.filter(chapter__colony=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset


class PledgeProgramListFilter(CompleteListFilter):
    class Meta:
        fields = ['region', 'year', 'term',
                  'manual', 'complete']
        model = PledgeProgram  # This is needed to automatically make year/term
        order_by = ['chapter']
