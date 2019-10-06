# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Ballot, BallotComplete
from regions.models import Region


class BallotFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    due_date = DateRangeFilter(field_name='due_date')

    class Meta:
        model = Ballot
        fields = ['name', 'due_date', 'type', 'voters']
        order_by = ['due_date']


class BallotCompleteFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        label="Region",
        choices=Region.region_choices(),
        method='filter_region'
    )

    class Meta:
        model = BallotComplete
        fields = ['region', 'motion',]
        order_by = ['ballot__due_date']

    def filter_region(self, queryset, field_name, value):
        if value == 'national':
            return queryset
        elif value == 'colony':
            queryset = queryset.filter(chapter__colony=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset
