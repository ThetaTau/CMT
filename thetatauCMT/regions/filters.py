# filters.py
import django_filters
from tasks.models import TaskDate


class RegionChapterTaskFilter(django_filters.FilterSet):
    class Meta:
        model = TaskDate
        fields = {
            'task__name': ['icontains'],
            'task__owner': ['icontains'],
            'date': ['lt', 'gt'],
            # 'complete': ['iexact']  # Did not work as difficult to filter
                  }
        order_by = ['date']
