from django.conf import settings
import django_tables2 as tables
from django_tables2.utils import A


class UserTable(tables.Table):
    name = tables.LinkColumn('users:detail',
                             args=[A('username')])
    status = tables.Column(empty_values=(),
                           verbose_name='Status')
    role = tables.Column(empty_values=(),
                         verbose_name='Role')

    class Meta:
        model = settings.AUTH_USER_MODEL
        fields = ('name', 'badge_number', 'email',
                  'major', 'graduation_year', 'phone_number',
                  'status', 'role')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no members matching the search criteria..."

    def render_status(self, record):
        return record.get_current_status()

    def render_role(self, record):
        return record.get_current_role()
