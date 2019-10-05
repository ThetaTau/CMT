import django_tables2 as tables
from django_tables2.utils import A
from .models import Ballot, BallotComplete


class BallotTable(tables.Table):
    name = tables.LinkColumn('ballots:detail', args=[A('slug')])

    class Meta:
        model = Ballot
        fields = ('name', 'type', 'due_date', 'voters',
                  'ayes', 'nays', 'abstains',
                  # 'incomplete',
                  )
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no ballots matching the search criteria..."


class BallotCompleteTable(tables.Table):
    ballot = tables.LinkColumn('ballots:details', args=[A('slug')])

    class Meta:
        model = BallotComplete
        fields = ('ballot', 'user', 'user__chapter',
                  'user__chapter__region', 'motion', 'role')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no ballots matching the search criteria..."
