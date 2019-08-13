# filters.py
import django_filters
from .models import User, UserStatusChange, UserRoleChange
from regions.models import Region


class UserListFilter(django_filters.FilterSet):
    current_status = django_filters.ChoiceFilter(
        choices=[
            ('active', 'active'),
            ('pnm', 'prospective'),
            ],
        method='filter_current_status'
    )

    class Meta:
        model = User
        fields = {'name': ['icontains'],
                  'current_status': ['exact'],
                  'major': ['icontains'],
                  'graduation_year': ['icontains'],
                  }
        order_by = ['name']

    def filter_current_status(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(current_status=value)
        return queryset


class UserRoleListFilter(django_filters.FilterSet):
    current_status = django_filters.ChoiceFilter(
        choices=[
            ('active', 'active'),
            ('pnm', 'prospective'),
            ],
        method='filter_current_status'
    )
    role = django_filters.MultipleChoiceFilter(
        choices=UserRoleChange.ROLES,
        method='filter_role'
    )
    region = django_filters.ChoiceFilter(
        choices=Region.region_choices(),
        method='filter_region'
    )

    class Meta:
        model = User
        fields = {'name': ['icontains'],
                  'current_status': ['exact'],
                  'major': ['icontains'],
                  'graduation_year': ['icontains'],
                  'chapter': ['exact'],
                  }
        order_by = ['name']

    def filter_current_status(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(current_status=value)
        return queryset

    def filter_role(self, queryset, field_name, value):
        if value:
            queryset = queryset.filter(role__in=value)
        return queryset

    def filter_region(self, queryset, field_name, value):
        if value == 'national':
            return queryset
        elif value == 'colony':
            queryset = queryset.filter(chapter__colony=True)
        else:
            queryset = queryset.filter(chapter__region__slug=value)
        return queryset
