# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Submission
from scores.models import ScoreType


class SubmissionListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    date = DateRangeFilter(name='date')
    type = django_filters.ModelChoiceFilter(
        queryset=ScoreType.objects.filter(type="Sub").all())

    class Meta:
        model = Submission
        fields = ['name', 'date',
                  'type',]
        order_by = ['date']
