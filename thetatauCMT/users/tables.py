from django.conf import settings
import django_tables2 as tables
from django_tables2.utils import A
from .models import User


class UserTable(tables.Table):
    name = tables.LinkColumn('users:detail',
                             args=[A('username')])

    class Meta:
        model = User
        fields = ('name', 'badge_number', 'email',
                  'major', 'graduation_year', 'phone_number',
                  'current_status', 'role', 'role_end')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no members matching the search criteria...\n" +\
                     "Only officers can view alumni contact information."
