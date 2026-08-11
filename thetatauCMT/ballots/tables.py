import django_tables2 as tables
from django_tables2.utils import A

from core.tables import CMTTable

from .models import Ballot, BallotComplete

# Columns that reveal how people voted; hidden from everyone except the Grand
# Regent and Grand Scribe (see ``models.can_view_ballot_results``).
RESULT_COLUMNS = ("ayes", "nays", "abstains")


class BallotTable(CMTTable):
    name = tables.LinkColumn("ballots:detail", args=[A("slug")])
    submitted = tables.Column(verbose_name="Ballots Returned")

    class Meta:
        model = Ballot
        fields = (
            "name",
            "type",
            "due_date",
            "voters",
            "submitted",
            "ayes",
            "nays",
            "abstains",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no ballots matching the search criteria..."

    def render_voters(self, value):
        return ", ".join(val[1] for val in Ballot.VOTERS if val[0] in value)

    def render_type(self, value):
        return Ballot.TYPES.get_value(value)


class BallotCompleteTable(CMTTable):
    status = tables.Column(accessor="motion", verbose_name="Ballot Returned", orderable=False)

    class Meta:
        model = BallotComplete
        # No motion column at any permission level: the vote itself is secret.
        fields = ("user_name", "chapter", "region", "role", "status")
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no ballots matching the search criteria..."

    def render_status(self, value):
        return "Not submitted" if str(value).lower() == "incomplete" else "Submitted"

    def render_role(self, value):
        return value.title()


class BallotUserTable(CMTTable):
    name = tables.LinkColumn("ballots:vote", args=[A("slug")])

    class Meta:
        model = Ballot
        fields = (
            "name",
            "type",
            "due_date",
            "motion",
        )
        attrs = {"class": "table table-striped table-bordered"}
        empty_text = "There are no ballots matching the search criteria..."

    def render_motion(self, value):
        return BallotComplete.MOTION.get_value(value)

    def render_type(self, value):
        return Ballot.TYPES.get_value(value)
