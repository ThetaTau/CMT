# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Event
from chapters.models import Chapter
from regions.models import Region
from scores.models import ScoreType


class EventListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    date = DateRangeFilter(field_name="date")
    type = django_filters.ModelChoiceFilter(
        queryset=ScoreType.objects.filter(type="Evt").all()
    )

    class Meta:
        model = Event
        fields = [
            "name",
            "date",
            "type",
        ]
        order_by = ["date"]

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
            self.base_filters["pictures"] = django_filters.ChoiceFilter(
                label="Pictures",
                choices=((True, "1+"), (False, "None")),
                method="filter_pictures",
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

    def filter_pictures(self, queryset, field_name, value):
        if value == "True":
            queryset = queryset.filter(pictures__isnull=False).distinct()
        elif value == "False":
            queryset = queryset.filter(pictures__isnull=True)
        return queryset
