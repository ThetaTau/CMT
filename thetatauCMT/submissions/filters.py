# filters.py
import django_filters
from .models import Submission
from scores.models import ScoreType


class SubmissionListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    date = django_filters.NumberFilter(name='date', lookup_expr='year')
    type = django_filters.ModelChoiceFilter(
        queryset=ScoreType.objects.filter(type="Sub").all())

    class Meta:
        model = Submission
        fields = ['name', 'date',
                  'type',]
        order_by = ['date']
