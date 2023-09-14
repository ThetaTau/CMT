# filters.py
import django_filters
from core.filters import DateRangeFilter
from tasks.models import TaskDate
from users.models import Role


class RegionChapterTaskFilter(django_filters.FilterSet):
    task__name = django_filters.CharFilter(lookup_expr="icontains")
    date = DateRangeFilter(field_name="date")
    task__owner = django_filters.MultipleChoiceFilter(
        choices=Role.roles_in_group_choices()
    )

    class Meta:
        model = TaskDate
        fields = [
            "task__name",
            "task__owner",
            "date",
            # 'complete': ['iexact']  # Did not work as difficult to filter
        ]
        order_by = ["date"]
