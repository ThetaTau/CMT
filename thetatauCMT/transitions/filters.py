"""TRWI-9: compliance dashboard filters. TRWI-11: search & trend filters."""

import django_filters

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region

from .models import POSITION_KEY_CHOICES, TAG_CHOICES, ReportObligation, TransitionReport
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


class SubmittedCycleFilterMixin:
    """Shared cycle filter method for TransitionReport-backed filters
    (TRWI-11) -- filters submitted_at (when the report was submitted), not
    due_date (an obligation-only field): search/trends are about the
    report's own content, not the obligation that spawned it.
    """

    def filter_cycle(self, queryset, field_name, value):
        start, end = get_cycle_bounds(value)
        if start is None:
            return queryset
        return queryset.filter(submitted_at__date__gte=start, submitted_at__date__lt=end)


class SearchFilter(SubmittedCycleFilterMixin, django_filters.FilterSet):
    """Cleans/renders GET params for the search view (TRWI-11) -- bound to a
    throwaway/empty queryset (mirrors ComplianceRateFilter's own
    ReportObligation.objects.none() trick): the real filtering/access
    control happens in services.search_reports, which needs the cleaned
    values, not a filterset-refined queryset. cycle defaults to "All time"
    (views._default_search_cycle), not "current" like the compliance
    dashboards -- search is for mining past institutional knowledge, so
    hiding prior cycles by default would work against its own purpose.
    """

    q = django_filters.CharFilter(label="Search")
    position_key = django_filters.ChoiceFilter(label="Position", choices=POSITION_KEY_CHOICES)
    tag = django_filters.ChoiceFilter(label="Tag", choices=TAG_CHOICES)
    cycle = django_filters.ChoiceFilter(label="Cycle", choices=CYCLE_CHOICES, method="filter_cycle", empty_label=None)

    class Meta:
        model = TransitionReport
        fields = ["q", "position_key", "tag", "cycle"]


class NationalSearchFilter(SearchFilter):
    """Adds chapter/region narrow-downs -- shown only to viewers whose read
    access already spans more than their own chapter (RD/National
    Officer/Admin); a Regent or successor's search is already locked to
    their own chapter by get_readable_reports.
    """

    chapter = django_filters.ModelChoiceFilter(label="Chapter", queryset=Chapter.objects.filter(active=True))
    region = django_filters.ModelChoiceFilter(
        label="Region", queryset=Region.objects.all(), field_name="chapter__region"
    )

    class Meta(SearchFilter.Meta):
        fields = ["q", "position_key", "chapter", "region", "tag", "cycle"]


class TrendFilter(SubmittedCycleFilterMixin, django_filters.FilterSet):
    """Cleans/renders GET params for the national trend view (TRWI-11) --
    bound to a throwaway/empty queryset, same reasoning as SearchFilter --
    services.get_tag_frequency/get_chapters_with_no_submissions need the
    cleaned values, not a filterset-refined queryset.
    """

    position_key = django_filters.ChoiceFilter(label="Position", choices=POSITION_KEY_CHOICES)
    region = django_filters.ModelChoiceFilter(
        label="Region", queryset=Region.objects.all(), field_name="chapter__region"
    )
    cycle = django_filters.ChoiceFilter(label="Cycle", choices=CYCLE_CHOICES, method="filter_cycle", empty_label=None)

    class Meta:
        model = TransitionReport
        fields = ["position_key", "region", "cycle"]
