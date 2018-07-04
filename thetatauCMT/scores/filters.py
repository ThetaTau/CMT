# filters.py
import django_filters
from .models import ScoreType


class ScoreListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = ScoreType
        fields = ['name', 'section',
                  'type',
                  ]
        order_by = ['name']
