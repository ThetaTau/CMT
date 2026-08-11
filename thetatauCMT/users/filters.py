# filters.py
import django_filters

from core.filters import DateRangeFilter, DynamicScopeFilterSetMixin
from core.models import ACTIVE_STATUSES
from thetatauCMT.chapters.models import Chapter, ChapterCurricula
from thetatauCMT.regions.models import Region

from .models import User, UserOrgParticipate, UserRoleChange


class UserListFilterBase(django_filters.FilterSet):
    current_status = django_filters.MultipleChoiceFilter(
        choices=[
            ("active", "Active"),
            ("pnm", "Prospective"),
            ("away", "Away"),
            ("activepend", "Active Pending"),
            ("alumnipend", "Alumni Pending"),
        ],
        method="filter_current_status",
    )
    major = django_filters.ModelChoiceFilter(
        queryset=ChapterCurricula.objects.none(),
        method="filter_major",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "major": ["exact"],
            "graduation_year": ["icontains", "gte", "lte"],
            "badge_number": ["gte", "lte"],
        }
        order_by = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["major"].queryset = ChapterCurricula.objects.filter(chapter=self.request.user.current_chapter)
        self.filters["graduation_year__icontains"].label = "Grad Year"
        self.filters["graduation_year__gte"].label = "Grad Year \u2265"
        self.filters["graduation_year__lte"].label = "Grad Year \u2264"
        self.filters["badge_number__gte"].label = "Badge # \u2265"
        self.filters["badge_number__lte"].label = "Badge # \u2264"
        if self.request.user.chapter_officer():
            self.filters["current_status"].field.choices.choices.extend(
                [
                    ("alumni", "Alumni"),
                    ("suspended", "Suspended"),
                    ("other", "Other Status"),
                ]
            )

    def filter_current_status(self, queryset, field_name, value):
        if value:
            if "active" in value:
                value.append("activeCC")
            if "alumni" in value:
                value.extend(["alumniCC", "deceased"])
            if "suspended" in value:
                value.extend(["pendexpul", "probation"])
            if "other" in value:
                value.extend(
                    [
                        "advisor",
                        "expelled",
                        "friend",
                        "nonmember",
                        "resigned",
                        "resignedCC",
                    ]
                )
            queryset = queryset.filter(current_status__in=value)
        return queryset

    def filter_major(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(major=value)
        return queryset


class UserListFilter(UserListFilterBase):
    rmp_complete = django_filters.ChoiceFilter(
        label="RMP Status",
        choices=[
            ("True", "Complete"),
            ("False", "Incomplete"),
        ],
    )


class UserRoleListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    current_status = django_filters.ChoiceFilter(
        choices=[
            ("active", "active"),
            ("pnm", "prospective"),
        ],
        method="filter_current_status",
    )
    current_roles = django_filters.MultipleChoiceFilter(choices=UserRoleChange.ROLES, method="filter_current_roles")
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")
    major = django_filters.ModelChoiceFilter(
        queryset=ChapterCurricula.objects.none(),
        method="filter_major",
    )
    chapter = django_filters.ChoiceFilter(
        label="Chapter",
        choices=Chapter.chapter_choices(),
        method="filter_chapter",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "major": ["exact"],
            "graduation_year": ["icontains", "gte", "lte"],
            "badge_number": ["gte", "lte"],
            "chapter": ["exact"],
        }
        order_by = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["major"].queryset = ChapterCurricula.objects.values_list(
            "major",
            flat=True,
        ).distinct()
        self.filters["graduation_year__icontains"].label = "Grad Year"
        self.filters["graduation_year__gte"].label = "Grad Year \u2265"
        self.filters["graduation_year__lte"].label = "Grad Year \u2264"
        self.filters["badge_number__gte"].label = "Badge # \u2265"
        self.filters["badge_number__lte"].label = "Badge # \u2264"

    def filter_current_status(self, queryset, field_name, value):
        if value:
            if value == "active":
                values = ["active", "activeCC"]
            else:
                values = ["pnm"]
            queryset = queryset.filter(current_status__in=values)
        return queryset

    def filter_current_roles(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(current_roles__overlap=value)
        return queryset

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset

    def filter_major(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(major__major=value.major)
        return queryset

    def filter_chapter(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(chapter__slug=value)
        return queryset


class AdvisorListFilter(DynamicScopeFilterSetMixin, django_filters.FilterSet):
    region = django_filters.ChoiceFilter(label="Region", choices=Region.region_choices(), method="filter_region")
    chapter = django_filters.ChoiceFilter(
        label="Chapter",
        choices=Chapter.chapter_choices(),
        method="filter_chapter",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "chapter": ["exact"],
        }
        order_by = ["name"]

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "candidate_chapter":
            queryset = queryset.filter(chapter__candidate_chapter=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset

    def filter_chapter(self, queryset, field_name, value):
        # The declared ``chapter`` ChoiceFilter references this method; without
        # it django-filter raised AssertionError when the advisor list rendered
        # (issue #827).
        if value:
            queryset = queryset.filter(chapter__slug=value)
        return queryset


ALUMNI_STATUSES = ["alumni", "alumniCC"]


class UserOrgListFilter(django_filters.FilterSet):
    """Filter the chapter external-organization table.

    Mirrors the events list filter: a member-status toggle (defaulting to
    active members), an organization-name search, and start/end date ranges.
    """

    status = django_filters.ChoiceFilter(
        label="Member Status",
        choices=(("active", "Active"), ("alumni", "Alumni"), ("all", "All")),
        method="filter_status",
        empty_label=None,
    )
    organization = django_filters.CharFilter(
        field_name="organization__name",
        lookup_expr="icontains",
        label="Organization",
    )
    start = DateRangeFilter(field_name="start", label="Start")
    end = DateRangeFilter(field_name="end", label="End")

    class Meta:
        model = UserOrgParticipate
        fields = ["status", "organization", "start", "end"]
        order_by = ["-start"]

    def __init__(self, data=None, *args, **kwargs):
        # Default to showing active members' participation when the page loads
        # with no explicit status choice (including after "Clear").
        if data is not None:
            data = data.copy()
            data.setdefault("status", "active")
        super().__init__(data, *args, **kwargs)

    def filter_status(self, queryset, field_name, value):
        if value == "active":
            return queryset.filter(user__current_status__in=ACTIVE_STATUSES)
        if value == "alumni":
            return queryset.filter(user__current_status__in=ALUMNI_STATUSES)
        return queryset
