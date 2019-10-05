# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Ballot, BallotComplete


class BallotFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    due_date = DateRangeFilter(field_name='date')

    class Meta:
        model = Ballot
        fields = ['name', 'due_date', 'type', 'voters']
        order_by = ['due_date']


class BallotCompleteFilter(django_filters.FilterSet):
    ballot__name = django_filters.CharFilter(lookup_expr='icontains')
    ballot__due_date = DateRangeFilter(field_name='ballot__due_date')

    class Meta:
        model = BallotComplete
        fields = ['ballot__name', 'ballot__due_date', 'user__chapter__region',
                  'motion', 'ballot__type', 'ballot__voters']
        order_by = ['ballot__due_date']
