# filters.py
import django_filters

from core.filters import DateRangeFilter, DynamicScopeFilterSetMixin
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region

from .models import Invoice


class InvoiceListFilter(django_filters.FilterSet):
    due_date = DateRangeFilter(field_name="due_date")

    class Meta:
        model = Invoice
        fields = [
            "due_date",
        ]
        order_by = ["-due_date"]


class ChapterBalanceListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")

    class Meta:
        model = Chapter
        fields = [
            "region",
        ]

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(candidate_chapter=True)
        else:
            queryset = queryset.filter(region__slug=value)
        return queryset
