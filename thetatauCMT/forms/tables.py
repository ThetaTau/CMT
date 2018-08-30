import django_tables2 as tables
from .models import Guard, Badge


class GuardTable(tables.Table):
    class Meta:
        model = Guard
        fields = ('name', 'cost', 'description',
                  'letters',
                  )
        attrs = {"class": "table-striped table-bordered"}


class BadgeTable(tables.Table):
    class Meta:
        model = Badge
        fields = ('name', 'cost', 'description',
                  )
        attrs = {"class": "table-striped table-bordered"}
