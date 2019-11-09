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

    def render_voters(self, value):
        return Ballot.VOTERS.get_value(value)

    def render_type(self, value):
        return Ballot.TYPES.get_value(value)


class BallotCompleteTable(tables.Table):
    class Meta:
        model = BallotComplete
        fields = ('user_name', 'chapter',
                  'region', 'motion', 'role')
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no ballots matching the search criteria..."

    def render_motion(self, value):
        return BallotComplete.MOTION.get_value(value)

    def render_role(self, value):
        return value.title()


class BallotUserTable(tables.Table):
    name = tables.LinkColumn('ballots:vote', args=[A('slug')])

    class Meta:
        model = Ballot
        fields = ('name', 'type', 'due_date', 'motion',
                  )
        attrs = {"class": "table-striped table-bordered"}
        empty_text = "There are no ballots matching the search criteria..."

    def render_motion(self, value):
        return BallotComplete.MOTION.get_value(value)

    def render_type(self, value):
        return Ballot.TYPES.get_value(value)
