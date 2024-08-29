# filters.py
import django_filters
from flake8.main.vcs import choices
from material.frontend.templatetags.material_frontend import verbose_name

from core.filters import DateRangeFilter
from django.forms.widgets import NumberInput
from .models import Audit, Bylaws, PledgeProgram, HSEducation, AlumniExclusion
from chapters.models import Chapter
from regions.models import Region


class AuditListFilter(django_filters.FilterSet):
    modified = DateRangeFilter()
    chapter = django_filters.ChoiceFilter(
        label="Chapter",
        choices=Chapter.chapter_choices(),
        method="filter_chapter",
    )

    class Meta:
        model = Audit
        fields = [
            "modified",
            "chapter",
            "user__chapter__region",
            "debit_card",
        ]
        order_by = ["user__chapter"]

    def filter_chapter(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(user__chapter__slug=value)
        return queryset


class CompleteListFilter(django_filters.FilterSet):
    complete = django_filters.ChoiceFilter(
        label="Complete",
        method="filter_complete",
        choices=(
            ("1", "Complete"),
            ("0", "Incomplete"),
            ("", "All"),
        ),
    )
    region = django_filters.ChoiceFilter(
        label="Region", choices=Region.region_choices(), method="filter_region"
    )

    class Meta:
        model = PledgeProgram  # This is needed to automatically make year/term
        fields = ["region", "year", "term", "complete"]
        order_by = ["chapter"]

    def filter_complete(self, queryset, field_name, value):
        return queryset

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset


class PledgeProgramListFilter(CompleteListFilter):
    class Meta:
        fields = ["region", "year", "term", "manual", "complete"]
        model = PledgeProgram  # This is needed to automatically make year/term
        order_by = ["chapter"]


class AlumniExclusionListFilter(django_filters.FilterSet):
    user = django_filters.CharFilter(
        label="Excluded Alumni", field_name="user__name", lookup_expr="icontains"
    )
    region = django_filters.ChoiceFilter(
        label="Region", choices=Region.region_choices(), method="filter_region"
    )
    regional_director_veto = django_filters.ChoiceFilter(
        label="RD Review",
        choices=((True, "Approved"), (False, "Vetoed"), ("None", "Not Reviewed")),
    )

    class Meta:
        fields = [
            "user",
            "region",
            "chapter",
            "regional_director_veto",
        ]
        model = AlumniExclusion
        order_by = ["chapter"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form.initial["regional_director_veto"] = None

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset


class RiskListFilter(django_filters.FilterSet):
    year = django_filters.NumberFilter(
        min_value=1990,
        max_value=2050,
        max_digits=4,
        decimal_places=0,
        widget=NumberInput(attrs={"placeholder": "Year"}),
        label="",
    )
    term = django_filters.ChoiceFilter(
        label="Term",
        choices=(("fa", "Fall"), ("sp", "Spring")),
    )
    region = django_filters.ChoiceFilter(
        label="Region", choices=Region.region_choices()
    )

    class Meta:
        fields = ["region", "term", "year"]
        model = Chapter  # This is needed to automatically make year/term
        order_by = ["chapter"]


class EducationListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        label="Region", choices=Region.region_choices(), method="filter_region"
    )
    program_date = DateRangeFilter()

    class Meta:
        model = HSEducation  # This is needed to automatically make year/term
        fields = ["region", "program_date"]
        order_by = ["chapter"]

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset


class BylawsListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        label="Region", choices=Region.region_choices(), method="filter_region"
    )

    class Meta:
        model = Bylaws  # This is needed to automatically make year/term
        fields = ["region"]
        order_by = ["chapter"]

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset
