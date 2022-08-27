# filters.py
import django_filters
from core.filters import DateRangeFilter
from .models import Invoice
from regions.models import Region


class InvoiceListFilter(django_filters.FilterSet):
    due_date = DateRangeFilter(field_name="due_date")

    class Meta:
        model = Invoice
        fields = [
            "due_date",
        ]
        order_by = ["-due_date"]


class ChapterBalanceListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        label="Region", choices=Region.region_choices(), method="filter_region"
    )

    class Meta:
        model = Invoice
        fields = [
            "region",
        ]

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset
