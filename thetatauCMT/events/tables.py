import django_tables2 as tables
from django_tables2.utils import A
from .models import Event


class EventTable(tables.Table):
    account_number = tables.LinkColumn('customer-detail', args=[A('pk')])
    customer_first_name = tables.LinkColumn('customer-detail', args=[A('pk')])
    customer_last_name = tables.LinkColumn('customer-detail', args=[A('pk')])
    customer_email = tables.LinkColumn('customer-detail', args=[A('pk')])

    class Meta:
        model = Event
        fields = ('name', 'date',
                  'type', 'score', 'description',
                  'duration', 'stem', 'host', 'miles')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no events matching the search criteria..."
