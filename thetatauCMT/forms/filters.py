# filters.py
import django_filters
from django.forms.widgets import NumberInput

from core.filters import DateRangeFilter, DynamicScopeFilterSetMixin
from core.models import CHAPTER_ROLES_CHOICES, NAT_OFFICERS_CHOICES, TODAY_END
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region
from thetatauCMT.users.models import UserRoleChange

from .models import AlumniExclusion, Audit, Bylaws, HSEducation, PledgeProgram, StatusChange


class AuditListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
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


class CompleteListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    complete = django_filters.ChoiceFilter(
        label="Complete",
        method="filter_complete",
        choices=(
            ("1", "Complete"),
            ("0", "Incomplete"),
            ("", "All"),
        ),
    )
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")

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


class AlumniExclusionListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    user = django_filters.CharFilter(label="Excluded Alumni", field_name="user__name", lookup_expr="icontains")
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")
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


class RiskListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
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
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices())

    class Meta:
        fields = ["region", "term", "year"]
        model = Chapter  # This is needed to automatically make year/term
        order_by = ["chapter"]


class EducationListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")
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


class StatusChangeListFilter(django_filters.FilterSet):
    """Chapter-scoped history of member status changes for one reason.

    Chapter scoping is applied by the view (``filter_user_chapter``); this only
    exposes member-name search and a change-date bucket. The reason is fixed by
    the page, so it is not a filter field.
    """

    user = django_filters.CharFilter(label="Member", field_name="user__name", lookup_expr="icontains")
    date_start = DateRangeFilter(label="Change Date")

    class Meta:
        model = StatusChange
        fields = ["user", "date_start"]


class GraduationListFilter(StatusChangeListFilter):
    degree = django_filters.ChoiceFilter(label="Degree", choices=[x.value for x in StatusChange.DEGREES])

    class Meta:
        model = StatusChange
        fields = ["user", "date_start", "degree"]


class BylawsListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")

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


class RoleChangeListFilter(django_filters.FilterSet):
    """Filter the chapter officer / role table.

    Chapter scoping is applied by the view (``filter_user_chapter``). Exposes a
    "Current Officers"/"All" toggle, a member-name search, a role multi-select,
    and start/end date-range buckets. The empty choice means "all (incl. past)";
    the view injects ``period=current`` on an unfiltered initial load, so the
    filter's "Clear" button truly clears it and shows all. "Current" mirrors
    ``UserRoleChange.get_current_roles`` (the term has not yet ended:
    ``end >= TODAY_END``).
    """

    period = django_filters.ChoiceFilter(
        label="Show",
        choices=(("current", "Current Officers"),),
        empty_label="All (incl. past)",
        method="filter_period",
    )
    user = django_filters.CharFilter(label="Member", field_name="user__name", lookup_expr="icontains")
    role = django_filters.MultipleChoiceFilter(label="Role", choices=CHAPTER_ROLES_CHOICES)
    start = DateRangeFilter(label="Start")
    end = DateRangeFilter(label="End")

    class Meta:
        model = UserRoleChange
        fields = ["period", "user", "role", "start", "end"]
        order_by = ["user__last_name", "-start"]

    def filter_period(self, queryset, field_name, value):
        if value == "current":
            return queryset.filter(end__gte=TODAY_END)
        return queryset


class RoleChangeNationalListFilter(RoleChangeListFilter):
    """National-officer variant: national role choices and a stricter "current".

    "Current" mirrors ``UserRoleChange.get_current_natoff`` — the term is active
    today (``start <= TODAY_END <= end``).
    """

    role = django_filters.MultipleChoiceFilter(label="Role", choices=NAT_OFFICERS_CHOICES)

    def filter_period(self, queryset, field_name, value):
        if value == "current":
            return queryset.filter(start__lte=TODAY_END, end__gte=TODAY_END)
        return queryset
