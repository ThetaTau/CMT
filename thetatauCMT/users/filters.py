# filters.py
import django_filters
from .models import User, UserStatusChange, UserRoleChange


class UserListFilter(django_filters.FilterSet):
    current_status = django_filters.ChoiceFilter(
        choices=[
            ('active', 'active'),
            ('pnm', 'prospective'),
            ],
        method='filter_current_status'
    )
    # Role looks ugly a huge block, and can simply be done in the chapter tab
    # role = django_filters.MultipleChoiceFilter(
    #     choices=UserRoleChange.ROLES,
    #     method='filter_role'
    # )

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
