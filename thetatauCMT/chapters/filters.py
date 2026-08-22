# filters.py
import django_filters

from .models import Chapter, Region


class ChapterListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices, method="filter_region")
    active = django_filters.ChoiceFilter(
        label="Status",
        method="filter_active",
        choices=(
            ("1", "Active"),
            ("0", "Inactive"),
            ("A", "All"),
        ),
    )

    class Meta:
        model = Chapter
        fields = {
            "name": ["icontains"],
            "region": ["exact"],
            "school": ["icontains"],
            "active": ["exact"],
        }
        order_by = ["name"]

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(candidate_chapter=True)
        else:
            queryset = queryset.filter(region__slug=value)
        return queryset

    def filter_active(self, queryset, field_name, value):
        if value == "0":
            return queryset.filter(active=False)
        if value == "A":
            return queryset
        # blank (unbound) or "1" -> Active
        return queryset.filter(active=True)
