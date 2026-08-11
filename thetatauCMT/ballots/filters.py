# filters.py
import django_filters

from core.filters import DateRangeFilter, DynamicScopeFilterSetMixin
from thetatauCMT.regions.models import Region

from .models import Ballot, BallotComplete, voter_role_query


class BallotFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    due_date = DateRangeFilter(field_name="due_date")
    # The generated filter matched the whole comma separated list exactly, so it
    # never matched a ballot with more than one voting role.
    voters = django_filters.ChoiceFilter(label="Voters", choices=Ballot.VOTERS, method="filter_voters")

    class Meta:
        model = Ballot
        fields = ["name", "due_date", "type", "voters"]
        order_by = ["due_date"]

    def filter_voters(self, queryset, field_name, value):
        return queryset.filter(voter_role_query(value))


class BallotUserFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    due_date = DateRangeFilter(field_name="due_date")

    class Meta:
        model = Ballot
        fields = [
            "name",
            "due_date",
        ]
        order_by = ["due_date"]


class BallotCompleteFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")
    status = django_filters.ChoiceFilter(
        label="Ballot Returned",
        choices=[("submitted", "Submitted"), ("incomplete", "Not submitted")],
        method="filter_status",
    )

    class Meta:
        model = BallotComplete
        fields = [
            "region",
            "motion",
            "status",
        ]
        order_by = ["ballot__due_date"]

    def __init__(self, *args, show_results=True, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtering by motion is itself a way to read the results, so voters who
        # may not see the votes only get a returned / not returned filter.
        self.filters.pop("status" if show_results else "motion", None)

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(user__chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(user__chapter__region__slug=value)
        return queryset

    def filter_status(self, queryset, field_name, value):
        # Rows that exist are, by definition, submitted; the "not submitted"
        # rows are synthesized by the view.
        return queryset.none() if value == "incomplete" else queryset
