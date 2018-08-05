# filters.py
import django_filters
from .models import TaskDate, Task


class TaskListFilter(django_filters.FilterSet):
    # name = django_filters.CharFilter(lookup_expr='icontains')
    # date = django_filters.NumberFilter(name='date', lookup_expr='year')
    # task__owner = django_filters.CharFilter(name='task__owner')
    # task__owner__iexact = django_filters.ModelChoiceFilter(
    #     lookup_expr='iexact',
    #     queryset=Task.objects.all().values_list("owner", flat=True).distinct())

    class Meta:
        model = TaskDate
        fields = {'task__owner': ['icontains'],
                  'date': ['lt', 'gt']
                  }
        order_by = ['date']
