# filters.py
import django_filters
from core.filters import DateRangeFilter
from core.models import ALL_ROLES_CHOICES
from tasks.models import TaskDate


class RegionChapterTaskFilter(django_filters.FilterSet):
    task__name = django_filters.CharFilter(lookup_expr="icontains")
    date = DateRangeFilter(field_name="date")
    task__owner = django_filters.MultipleChoiceFilter(choices=ALL_ROLES_CHOICES)

    class Meta:
        model = TaskDate
        fields = [
            "task__name",
            "task__owner",
            "date",
            # 'complete': ['iexact']  # Did not work as difficult to filter
        ]
        order_by = ["date"]
