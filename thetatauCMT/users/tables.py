import django_tables2 as tables
from django_tables2.utils import A
from .models import User


class UserTable(tables.Table):
    name = tables.LinkColumn('users:detail',
                             args=[A('username')])
    status = tables.Column(empty_values=(),
                           verbose_name='Status')
    role = tables.Column(empty_values=(),
                         verbose_name='Role')

    class Meta:
        model = User
        fields = ('name', 'badge_number',
                  'major', 'graduation_year', 'phone_number',
                  'status', 'role')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no members matching the search criteria..."

    def render_status(self, record):
        if record.status.exists():
            return record.get_current_status()

    def render_role(self, record):
        if record.status.exists():
            return record.get_current_role()
