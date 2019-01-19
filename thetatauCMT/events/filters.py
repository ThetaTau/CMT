# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Event
from scores.models import ScoreType


class EventListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    date = DateRangeFilter(name='date')
    type = django_filters.ModelChoiceFilter(
        queryset=ScoreType.objects.filter(type="Evt").all())

    class Meta:
        model = Event
        fields = ['name', 'date',
                  'type',]
        order_by = ['date']
