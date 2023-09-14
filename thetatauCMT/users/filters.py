# filters.py
import django_filters
from .models import User, UserRoleChange
from regions.models import Region
from chapters.models import ChapterCurricula, Chapter
from users.models import Role


class UserListFilterBase(django_filters.FilterSet):
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
    major = django_filters.ModelChoiceFilter(
        queryset=ChapterCurricula.objects.none(),
        method="filter_major",
    )

    class Meta:
        model = User
        fields = {
            "name": ["icontains"],
            "major": ["exact"],
            "graduation_year": ["icontains"],
        }
        order_by = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["major"].queryset = ChapterCurricula.objects.filter(
            chapter=self.request.user.current_chapter
        )

    def filter_current_status(self, queryset, field_name, value):
        if value:
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


class UserRoleListFilter(django_filters.FilterSet):
    current_status = django_filters.ChoiceFilter(
        choices=[
            ("active", "active"),
            ("pnm", "prospective"),
        ],
        method="filter_current_status",
    )
    current_roles = django_filters.MultipleChoiceFilter(
        choices=Role.roles_in_group_choices(), method="filter_current_roles"
    )
    region = django_filters.ChoiceFilter(
        choices=Region.region_choices(), method="filter_region"
    )
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
            "graduation_year": ["icontains"],
            "chapter": ["exact"],
        }
        order_by = ["name"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["major"].queryset = ChapterCurricula.objects.values_list(
            "major",
            flat=True,
        ).distinct()

    def filter_current_status(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(current_status=value)
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


class AdvisorListFilter(django_filters.FilterSet):
    region = django_filters.ChoiceFilter(
        choices=Region.region_choices(), method="filter_region"
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
