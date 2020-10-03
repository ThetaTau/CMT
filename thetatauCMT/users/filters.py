# filters.py
import django_filters
from .models import User, UserStatusChange, UserRoleChange
from regions.models import Region
from chapters.models import ChapterCurricula


class UserListFilter(django_filters.FilterSet):
    current_status = django_filters.MultipleChoiceFilter(
        choices=[
            ("active", "active"),
            ("pnm", "prospective"),
            ("alumni", "alumni"),
            ("activepend", "activepend"),
            ("alumnipend", "alumnipend"),
        ],
        method="filter_current_status",
    )
    major = django_filters.MultipleChoiceFilter(
        choices=ChapterCurricula.objects.none(), method="filter_major",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "current_status": ["exact"],
            "major": ["exact"],
            "graduation_year": ["icontains"],
        }
        order_by = ["name"]

    def filter_current_status(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(current_status__in=value)
        return queryset

    def filter_major(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(major__in=value)
        return queryset


class UserRoleListFilter(django_filters.FilterSet):
    current_status = django_filters.ChoiceFilter(
        choices=[("active", "active"), ("pnm", "prospective"),],
        method="filter_current_status",
    )
    role = django_filters.MultipleChoiceFilter(
        choices=UserRoleChange.ROLES, method="filter_role"
    )
    region = django_filters.ChoiceFilter(
        choices=Region.region_choices(), method="filter_region"
    )
    major = django_filters.MultipleChoiceFilter(
        choices=ChapterCurricula.objects.none(), method="filter_major",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "current_status": ["exact"],
            "major": ["exact"],
            "graduation_year": ["icontains"],
            "chapter": ["exact"],
        }
        order_by = ["name"]

    def filter_current_status(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(current_status=value)
        return queryset

    def filter_role(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(role__in=value)
        return queryset

    def filter_region(self, queryset, field_name, value):
        if value == "national":
            return queryset
        elif value == "colony":
            queryset = queryset.filter(chapter__colony=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset

    def filter_major(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(major__in=value)
        return queryset


class AdvisorListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        choices=Region.region_choices(), method="filter_region"
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
        elif value == "colony":
            queryset = queryset.filter(chapter__colony=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset
