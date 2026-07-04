# filters.py
import django_filters
from django.db.models import Exists, OuterRef

from core.filters import DateRangeFilter
from core.models import CHAPTER_OFFICER_CHOICES

from .models import TaskChapter, TaskDate


class TaskListFilter(django_filters.FilterSet):
    complete = django_filters.ChoiceFilter(
        method="filter_complete",
        choices=(
            ("1", "Complete"),
            ("0", "Incomplete"),
            ("A", "All"),
        ),
    )
    date = DateRangeFilter(field_name="date")
    task__owner = django_filters.MultipleChoiceFilter(choices=CHAPTER_OFFICER_CHOICES)

    class Meta:
        model = TaskDate
        fields = [
            "task__owner",
            "complete",
            "date",
        ]
        order_by = ["date"]

    def filter_complete(self, queryset, field_name, value):
        if not value or value == "A":
            return queryset
        chapter = self.request.user.current_chapter
        # Use Exists on a correlated subquery so that a TaskChapter created by
        # a *different* chapter cannot introduce duplicate rows or misclassify
        # the TaskDate for the current chapter.
        completed = TaskChapter.objects.filter(task=OuterRef("pk"), chapter=chapter)
        if value == "1":
            return queryset.filter(Exists(completed))
        # value == "0" → Incomplete for the current chapter
        return queryset.filter(~Exists(completed))
