# filters.py
import django_filters
from .models import User, UserStatusChange, UserRoleChange


class UserListFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr='icontains')
    # date = django_filters.NumberFilter(name='date', lookup_expr='year')
    # status = django_filters.MultipleChoiceFilter(
    #     choices=[
    #         (0, 'alumni'),
    #         (1, 'active'),
    #         (2, 'prospective'),
    #         ]
    # )
    # role = django_filters.MultipleChoiceFilter(
    #     choices=UserRoleChange.CHAPTER_OFFICER
    # )

    class Meta:
        model = User
        fields = ['name', 'badge_number',
                  'major', 'graduation_year',
                  # 'status',
                  # 'role',
                  ]
        order_by = ['badge_number']
