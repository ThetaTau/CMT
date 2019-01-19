# filters.py
import django_filters
from core.filters import DateRangeFilter
from core.models import CHAPTER_OFFICER_CHOICES
from .models import TaskDate, Task
from django.db import models


class TaskListFilter(django_filters.FilterSet):
    complete = django_filters.ChoiceFilter(
        method='filter_complete',
        choices=(
               ('1', 'Complete'),
               ('0', 'Incomplete'),
               ('', 'All'),
        )
    )
    date = DateRangeFilter(name='date')
    task__owner = django_filters.MultipleChoiceFilter(
        choices=CHAPTER_OFFICER_CHOICES)

    class Meta:
        model = TaskDate
        fields = ['task__owner',
                  'complete',
                  'date',
                  ]
        order_by = ['date']

    def filter_complete(self, queryset, field_name, value):
        if value:
            chapter = self.request.user.current_chapter
            queryset = queryset.annotate(
                complete_result=models.Case(
                    models.When(
                        models.Q(chapters__chapter=chapter), models.Value('1')
                    ),
                    default=models.Value('0'),
                    output_field=models.CharField()
                )
            )
            queryset = queryset.filter(complete_result=value)
        return queryset
