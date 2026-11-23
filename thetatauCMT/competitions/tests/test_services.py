import datetime

import pytest
from django.utils import timezone

from .. import services
from ..models import Entry, Judge, KeyDate
from .factories import (
    CompetitionFactory,
    EntryFactory,
    JudgeFactory,
    ParticipantFactory,
    RoundFactory,
    RubricCriterionFactory,
    SubmissionItemFactory,
    eastern,
)


def test_year_labels_and_dates_move_one_year():
    assert services.next_year_label("2026-2027") == "2027-2028"
    assert services.next_year_label("2027") == "2028"
    assert services.next_year_label("Pilot") == "Pilot (copy)"
    assert services.a_year_later(datetime.date(2028, 2, 29)) == datetime.date(2029, 2, 28)


@pytest.mark.django_db
def test_copying_to_a_new_year_copies_the_setup_only(admin_user):
    competition = CompetitionFactory(
        year_label="2026-2027",
        slug="necc-2026-2027",
        # Daylight saving time has started on March 10, 2026 but not on March 10, 2027.
        intent_opens_at=eastern(2026, 3, 10, 12),
        intent_closes_at=eastern(2026, 9, 28, 23, 59, 59),
    )
    KeyDate.objects.create(competition=competition, date=datetime.date(2026, 9, 22), label="PD Chair call")
    proposal = RoundFactory(
        competition=competition, rubric_locked_at=timezone.now(), results_published_at=timezone.now()
    )
    final = RoundFactory(
        competition=competition,
        number=2,
        name="Final submission",
        selection="places",
        eligibility="advanced",
        places=2,
        opens_at=eastern(2027, 5, 21),
        closes_at=eastern(2027, 5, 28, 23, 59, 59),
        judging_closes_at=eastern(2027, 6, 25, 23, 59, 59),
    )
    RubricCriterionFactory(round=proposal, name="Technical Rigor & Analysis", max_points=5)
    SubmissionItemFactory(round=final, label="Grant spending summary", file_types=["pdf", "spreadsheet"])
    ParticipantFactory(competition=competition)
    EntryFactory(round=proposal)
    JudgeFactory(round=proposal)

    copy = services.copy_to_next_year(competition, by=admin_user)

    assert (copy.year_label, copy.slug, copy.is_published, copy.created_by) == (
        "2027-2028",
        "necc-2027-2028",
        False,
        admin_user,
    )
    assert copy.case_title == competition.case_title
    assert copy.local(copy.intent_opens_at).replace(tzinfo=None) == datetime.datetime(2027, 3, 10, 12)
    assert copy.local(copy.intent_closes_at).replace(tzinfo=None) == datetime.datetime(2027, 9, 28, 23, 59, 59)
    assert list(copy.key_dates.values_list("date", "label")) == [(datetime.date(2027, 9, 22), "PD Chair call")]

    new_proposal, new_final = copy.rounds.all()
    assert copy.local(new_proposal.closes_at).replace(tzinfo=None) == datetime.datetime(2027, 12, 11, 23, 59, 59)
    assert copy.local(new_final.closes_at).replace(tzinfo=None) == datetime.datetime(2028, 5, 28, 23, 59, 59)
    assert (new_final.selection, new_final.eligibility, new_final.places) == ("places", "advanced", 2)
    assert new_proposal.rubric_locked_at is None
    assert new_proposal.results_published_at is None
    assert list(new_proposal.criteria.values_list("name", "max_points")) == [("Technical Rigor & Analysis", 5)]
    assert [(item.label, list(item.file_types)) for item in new_final.items.all()] == [
        ("Grant spending summary", ["pdf", "spreadsheet"])
    ]
    assert not copy.participants.exists()
    assert not Entry.objects.filter(round__competition=copy).exists()
    assert not Judge.objects.filter(round__competition=copy).exists()


@pytest.mark.django_db
def test_a_copy_never_takes_an_existing_slug():
    competition = CompetitionFactory(year_label="2026-2027", slug="necc-2026-2027")
    CompetitionFactory(year_label="2027-2028", slug="necc-2027-2028")

    assert services.copy_to_next_year(competition).slug == "necc-2027-2028-2"
