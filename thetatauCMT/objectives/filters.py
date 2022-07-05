import django_filters
from core.filters import DateRangeFilter
from regions.models import Region
from chapters.models import Chapter
from .models import Objective


class ObjectiveListFilter(django_filters.FilterSet):
    date = DateRangeFilter(field_name="date")

    class Meta:
        model = Objective
        fields = [
            "title",
            "complete",
            "date",
        ]
        order_by = ["-date"]

    def __init__(self, *args, **kwargs):
        natoff = kwargs.get("natoff", False)
        if natoff:
            kwargs.pop("natoff")
            self.base_filters["region"] = django_filters.ChoiceFilter(
                choices=Region.region_choices(), method="filter_region"
            )
            self.base_filters["chapter"] = django_filters.ChoiceFilter(
                label="Chapter",
                choices=Chapter.chapter_choices(),
                method="filter_chapter",
            )
        super().__init__(*args, **kwargs)

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset

    def filter_chapter(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(chapter__slug=value)
        return queryset
