import datetime

import pytest
from django.core.management import call_command

from ..models import Competition

pytestmark = pytest.mark.django_db


def test_this_years_fixture_loads_the_announcement_setup():
    call_command("loaddata", "necc_2026_2027", verbosity=0)
    call_command("loaddata", "necc_2026_2027", verbosity=0)

    competition = Competition.objects.get(slug="necc-2026-2027")
    proposal, final = competition.rounds.all()

    assert Competition.objects.filter(slug__startswith="necc-2026").count() == 1
    assert not competition.is_published
    assert competition.case_title == "Reduce energy usage in your community"
    assert competition.key_dates.count() == 8
    assert proposal.closes_at == datetime.datetime(2026, 12, 12, 4, 59, 59, tzinfo=datetime.timezone.utc)
    assert competition.format_time(proposal.opens_at) == "Fri, Dec 4, 2026, 12:00 am Eastern"
    assert competition.format_time(proposal.judging_closes_at) == "Fri, Jan 8, 2027, 11:59 pm Eastern"
    assert (proposal.eligibility, proposal.advance_per_region, proposal.advance_total) == ("participants", 2, 20)
    assert [criterion.max_points for criterion in proposal.criteria.all()] == [5] * 7
    assert [item.label for item in proposal.items.all()] == ["Proposal"]
    assert competition.format_time(final.closes_at) == "Fri, May 28, 2027, 11:59 pm Eastern"
    assert (final.eligibility, final.selection, final.places) == ("advanced", "places", 2)
    assert final.criteria.count() == 5
    assert [(item.label, item.required) for item in final.items.all()] == [
        ("Final report", True),
        ("Final presentation", True),
        ("Grant spending summary", True),
        ("Video", False),
    ]

    for row in [competition, *competition.key_dates.all(), proposal, final]:
        row.full_clean()
    for row in [*proposal.criteria.all(), *final.criteria.all(), *proposal.items.all(), *final.items.all()]:
        row.full_clean()
