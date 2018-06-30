# filters.py
import django_filters
from .models import Event


class EventListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    date = django_filters.NumberFilter(name='date', lookup_expr='year')
    class Meta:
        model = Event
        fields = ['name', 'date',
                  'type',]
        order_by = ['date']
