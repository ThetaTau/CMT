import datetime
import pytest
from django.utils.text import slugify
from thetatauCMT.ballots.models import Ballot, BallotComplete
from thetatauCMT.ballots.tests.factories import BallotFactory, BallotCompleteFactory
from thetatauCMT.users.tests.factories import UserFactory


# ---------------------------------------------------------------------------
# Ballot.TYPES enum
# ---------------------------------------------------------------------------

def test_ballot_types_get_value():
    assert Ballot.TYPES.get_value("chapter") == "Chapter Petition"
    assert Ballot.TYPES.get_value("suspension") == "Suspension"
    assert Ballot.TYPES.get_value("other") == "Other"


def _create_ballot(**kwargs):
    """Create a Ballot using direct construction.

    Ballot.save() is defined as ``def save(self):`` (no *args/**kwargs),
    so it cannot be created via ``objects.create()`` (which passes
    force_insert=True).  Always construct + .save() directly.
    """
    defaults = dict(
        name=f"Test Ballot {datetime.datetime.now().microsecond}",
        type="other",
        description="A test description",
        due_date=datetime.date.today() + datetime.timedelta(days=30),
        voters="grand regent",
    )
    defaults.update(kwargs)
    ballot = Ballot(**defaults)
    ballot.save()
    return ballot


# ---------------------------------------------------------------------------
# Ballot.__str__ and save
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_ballot_str():
    ballot = _create_ballot(name="Test Ballot")
    assert str(ballot) == "Test Ballot"


@pytest.mark.django_db
def test_ballot_save_sets_slug():
    ballot = _create_ballot(name="My Test Ballot")
    assert ballot.slug == slugify("My Test Ballot")


@pytest.mark.django_db
def test_ballot_save_with_all_chapters_creates_task():
    """Saving a ballot with 'all_chapters' in voters creates a Task."""
    from thetatauCMT.tasks.models import Task
    initial_task_count = Task.objects.count()
    ballot = Ballot(
        name="All Chapters Vote",
        type="other",
        description="A test ballot for all chapters",
        due_date=datetime.date.today() + datetime.timedelta(days=30),
        voters="all_chapters",
    )
    ballot.save()
    assert Task.objects.count() == initial_task_count + 1
    task = Task.objects.get(name="All Chapters Vote")
    assert task.owner == "regent"
    assert task.resource == "ballots:vote"


@pytest.mark.django_db
def test_ballot_save_without_all_chapters_no_task():
    """Saving a ballot without 'all_chapters' does NOT create a Task."""
    from thetatauCMT.tasks.models import Task
    initial_task_count = Task.objects.count()
    ballot = Ballot(
        name="Specific Vote",
        type="other",
        description="A test ballot for specific role",
        due_date=datetime.date.today() + datetime.timedelta(days=30),
        voters="grand regent",
    )
    ballot.save()
    assert Task.objects.count() == initial_task_count


# ---------------------------------------------------------------------------
# Ballot.ayes / nays / abstains
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_ballot_ayes_nays_abstains():
    ballot = _create_ballot(name="Vote Count Test", type="other", description="Testing vote counts")
    user1 = UserFactory.create()
    user2 = UserFactory.create()
    user3 = UserFactory.create()
    user4 = UserFactory.create()

    def _bc(user, motion):
        bc = BallotComplete(ballot=ballot, user=user, motion=motion, role="grand regent")
        bc.save()
        return bc

    _bc(user1, "aye")
    _bc(user2, "aye")
    _bc(user3, "nay")
    _bc(user4, "abstain")
    assert ballot.ayes == 2
    assert ballot.nays == 1
    assert ballot.abstains == 1


@pytest.mark.django_db
def test_ballot_ayes_empty():
    ballot = _create_ballot(name="Empty Vote", type="other", description="No votes yet")
    assert ballot.ayes == 0
    assert ballot.nays == 0
    assert ballot.abstains == 0


# ---------------------------------------------------------------------------
# Ballot.counts
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_ballot_counts_includes_all_ballots():
    for i in range(3):
        _create_ballot(name=f"Count Ballot {i}")
    counts = list(Ballot.counts())
    # counts() returns one entry per ballot via values()
    assert len(counts) >= 3
    for entry in counts[:3]:
        assert "ayes" in entry
        assert "nays" in entry
        assert "abstains" in entry


# ---------------------------------------------------------------------------
# Ballot.get_completed
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_ballot_get_completed_returns_none_when_not_voted():
    ballot = _create_ballot(name="Incomplete Ballot", type="other", description="testing")
    user = UserFactory.create()
    result = ballot.get_completed(user)
    assert result is None


@pytest.mark.django_db
def test_ballot_get_completed_returns_vote_when_voted():
    ballot = _create_ballot(name="Completed Ballot", type="other", description="testing")
    user = UserFactory.create()
    bc = BallotComplete(ballot=ballot, user=user, motion="aye", role="grand regent")
    bc.save()
    result = ballot.get_completed(user)
    assert result is not None
    assert result.motion == "aye"
