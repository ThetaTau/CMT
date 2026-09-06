"""TRWI-9: compliance dashboard filters."""

import django_filters

from thetatauCMT.regions.models import Region

from .models import POSITION_KEY_CHOICES, ReportObligation
from .services import CYCLE_CHOICES, get_cycle_bounds


class CycleFilterMixin:
    """Shared ``cycle`` filter method -- see ``services.get_cycle_bounds``."""

    def filter_cycle(self, queryset, field_name, value):
        start, end = get_cycle_bounds(value)
        if start is None:
            return queryset
        return queryset.filter(due_date__gte=start, due_date__lt=end)


class ObligationComplianceFilter(CycleFilterMixin, django_filters.FilterSet):
    """Filters the chapter dashboard's per-obligation table (TRWI-9)."""

    position_key = django_filters.ChoiceFilter(label="Position", choices=POSITION_KEY_CHOICES)
    status = django_filters.ChoiceFilter(label="Status", choices=[x.value for x in ReportObligation.Status])
    cycle = django_filters.ChoiceFilter(label="Cycle", choices=CYCLE_CHOICES, method="filter_cycle", empty_label=None)

    class Meta:
        model = ReportObligation
        fields = ["position_key", "status", "cycle"]


class ComplianceRateFilter(CycleFilterMixin, django_filters.FilterSet):
    """Filters the obligations queryset BEFORE
    ``services.get_chapter_compliance_stats`` aggregates it (TRWI-9 regional
    rates view) -- position + cycle only. The national view adds a region
    narrow-down; see ``NationalComplianceRateFilter``.
    """

    position_key = django_filters.ChoiceFilter(label="Position", choices=POSITION_KEY_CHOICES)
    cycle = django_filters.ChoiceFilter(label="Cycle", choices=CYCLE_CHOICES, method="filter_cycle", empty_label=None)

    class Meta:
        model = ReportObligation
        fields = ["position_key", "cycle"]


class NationalComplianceRateFilter(ComplianceRateFilter):
    """Adds a region narrow-down -- shown only to National Officers/Admins;
    an RD's own dashboard is already locked to their own region(s).
    """

    region = django_filters.ModelChoiceFilter(
        label="Region", queryset=Region.objects.all(), field_name="chapter__region"
    )

    class Meta(ComplianceRateFilter.Meta):
        fields = ["position_key", "region", "cycle"]
