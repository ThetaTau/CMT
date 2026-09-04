import datetime

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.utils.text import slugify

from thetatauCMT.ballots.models import Ballot, BallotComplete, can_view_ballot_results
from thetatauCMT.chapters.tests.factories import ChapterFactory
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


# ---------------------------------------------------------------------------
# save() signature / slug handling
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ballot_can_be_created_through_the_manager():
    """``save(self)`` broke ``objects.create()`` (it passes force_insert)."""
    ballot = Ballot.objects.create(
        name="Manager Ballot",
        type="other",
        description="testing",
        due_date=datetime.date.today() + datetime.timedelta(days=5),
        voters="grand regent",
    )
    assert ballot.pk
    assert ballot.slug == "manager-ballot"


@pytest.mark.django_db
def test_ballot_save_update_fields_does_not_crash():
    ballot = _create_ballot(name="Update Fields Ballot")
    ballot.sender = "Grand Regent"
    ballot.save(update_fields=["sender", "slug"])
    ballot.refresh_from_db()
    assert ballot.sender == "Grand Regent"


@pytest.mark.django_db
def test_reused_ballot_name_does_not_collide_on_the_task_slug():
    """A ballot re-run under the same name reuses the chapter task."""
    from thetatauCMT.tasks.models import Task, TaskDate

    first = _create_ballot(name="Annual Vote", voters=["all_chapters"])
    second_due = first.due_date + datetime.timedelta(days=365)
    second = Ballot(
        name="Annual Vote",
        type="other",
        description="second run",
        due_date=second_due,
        voters=["all_chapters"],
    )
    second.save()
    tasks = Task.objects.filter(name="Annual Vote")
    assert tasks.count() == 1
    assert TaskDate.objects.filter(task=tasks.first()).count() == 2


@pytest.mark.django_db
def test_editing_the_due_date_moves_the_chapter_task_date():
    from thetatauCMT.tasks.models import Task, TaskDate

    ballot = _create_ballot(name="Moving Ballot", voters=["all_chapters"])
    task = Task.objects.get(name="Moving Ballot")
    new_due = ballot.due_date + datetime.timedelta(days=7)
    ballot.due_date = new_due
    ballot.save()
    dates = list(TaskDate.objects.filter(task=task).values_list("date", flat=True))
    assert dates == [new_due]


@pytest.mark.django_db
def test_get_by_slug_returns_the_newest_ballot():
    older = _create_ballot(name="Repeat Ballot", due_date=datetime.date.today())
    newer = Ballot(
        name="Repeat Ballot",
        type="other",
        description="newer",
        due_date=datetime.date.today() + datetime.timedelta(days=10),
        voters="grand regent",
    )
    newer.save()
    assert older.slug == newer.slug
    assert Ballot.get_by_slug(newer.slug).pk == newer.pk
    assert Ballot.get_by_slug("no-such-ballot") is None


# ---------------------------------------------------------------------------
# Who may see the results
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "roles,expected",
    [
        (["grand regent"], True),
        (["grand scribe"], True),
        (["grand treasurer"], False),
        (["regional director"], False),
        (["regent"], False),
        ([], False),
        (None, False),
    ],
)
@pytest.mark.django_db
def test_can_view_ballot_results_by_role(roles, expected):
    user = UserFactory.create()
    user.current_roles = roles
    user.save()
    assert can_view_ballot_results(user) is expected


@pytest.mark.django_db
def test_can_view_ballot_results_false_for_anonymous():
    assert can_view_ballot_results(AnonymousUser()) is False


@pytest.mark.django_db
def test_can_view_ballot_results_false_for_admin():
    """A superuser is not a Grand Regent; the tallies are theirs alone."""
    user = UserFactory.create(is_superuser=True)
    user.current_roles = ["treasurer"]
    user.save()
    assert can_view_ballot_results(user) is False


@pytest.mark.django_db
def test_can_view_ballot_results_true_for_a_superuser_who_is_grand_regent():
    user = UserFactory.create(is_superuser=True)
    user.current_roles = ["grand regent"]
    user.save()
    assert can_view_ballot_results(user) is True


# ---------------------------------------------------------------------------
# Voting rules
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_roles_allowed_adds_only_regent_and_scribe():
    ballot = _create_ballot(name="Chapter Ballot", voters=["all_chapters"])
    assert set(ballot.roles_allowed) == {"all_chapters", "regent", "scribe"}


@pytest.mark.django_db
def test_treasurer_may_not_vote_a_chapter_ballot():
    ballot = _create_ballot(name="Treasurer Ballot", voters=["all_chapters"])
    user = UserFactory.create()
    user.current_roles = ["treasurer"]
    user.save()
    assert ballot.voting_roles_for(user) == []


@pytest.mark.django_db
def test_scribe_may_vote_a_chapter_ballot():
    ballot = _create_ballot(name="Scribe Ballot", voters=["all_chapters"])
    user = UserFactory.create()
    user.current_roles = ["scribe"]
    user.save()
    assert ballot.voting_roles_for(user) == ["scribe"]


@pytest.mark.django_db
def test_chapter_vote_finds_the_vote_cast_by_the_other_officer():
    ballot = _create_ballot(name="Shared Chapter Vote", voters=["all_chapters"])
    chapter = ChapterFactory.create()
    regent = UserFactory.create(chapter=chapter)
    BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent").save()
    assert ballot.chapter_vote(chapter).user == regent
    assert ballot.chapter_vote(ChapterFactory.create()) is None


@pytest.mark.django_db
def test_is_open_tracks_the_due_date():
    assert _create_ballot(name="Open Ballot").is_open
    past = _create_ballot(name="Closed Ballot", due_date=datetime.date.today() - datetime.timedelta(days=1))
    assert not past.is_open


@pytest.mark.django_db
def test_voting_closes_at_five_pm_pacific_on_the_due_date():
    ballot = _create_ballot(name="Five PM Ballot", due_date=datetime.date(2026, 8, 10))
    closes = ballot.closes_at
    assert closes.hour == 17
    assert closes.minute == 0
    assert closes.date() == datetime.date(2026, 8, 10)
    assert str(closes.tzinfo) == "America/Los_Angeles"
    assert ballot.closes_time_display.startswith("5:00 pm P")
    assert ballot.closes_display.startswith("Aug 10, 2026 at 5:00 pm P")


@pytest.mark.django_db
def test_ballot_is_open_until_five_pm_and_closed_after(freeze_close):
    ballot = _create_ballot(name="Cutoff Ballot", due_date=timezone.localdate())
    with freeze_close(ballot, minutes_before=30):
        assert ballot.is_open
    with freeze_close(ballot, minutes_after=30):
        assert not ballot.is_open


@pytest.mark.django_db
def test_open_ballots_drops_todays_ballots_after_the_cutoff(freeze_close):
    ballot = _create_ballot(name="Cutoff Query Ballot", due_date=timezone.localdate())
    with freeze_close(ballot, minutes_before=30):
        assert ballot in Ballot.open_ballots()
    with freeze_close(ballot, minutes_after=30):
        assert ballot not in Ballot.open_ballots()


@pytest.mark.django_db
def test_vote_choices_exclude_incomplete():
    assert "incomplete" not in [value for value, _ in BallotComplete.VOTE_CHOICES]


# ---------------------------------------------------------------------------
# Ballot.user_ballots role matching
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_ballots_does_not_match_a_role_substring():
    """A chapter Regent must not be handed the Grand Regent's ballot."""
    grand = _create_ballot(name="Grand Only Ballot", voters=["grand regent"])
    user = UserFactory.create()
    user.current_roles = ["regent"]
    user.save()
    assert grand.pk not in [ballot["pk"] for ballot in Ballot.user_ballots(user)]


@pytest.mark.django_db
def test_user_ballots_includes_all_chapters_for_a_regent():
    ballot = _create_ballot(name="All Chapters Regent Ballot", voters=["all_chapters"])
    user = UserFactory.create()
    user.current_roles = ["regent"]
    user.save()
    assert ballot.pk in [entry["pk"] for entry in Ballot.user_ballots(user)]


@pytest.mark.django_db
def test_user_ballots_shows_the_chapter_vote_to_the_other_officer():
    ballot = _create_ballot(name="Chapter Vote Visible", voters=["all_chapters"])
    chapter = ChapterFactory.create()
    regent = UserFactory.create(chapter=chapter)
    BallotComplete(ballot=ballot, user=regent, motion="nay", role="regent").save()
    scribe = UserFactory.create(chapter=chapter)
    scribe.current_roles = ["scribe"]
    scribe.save()
    entry = [item for item in Ballot.user_ballots(scribe) if item["pk"] == ballot.pk][0]
    assert entry["motion"] == "nay"


# ---------------------------------------------------------------------------
# Outstanding voters
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_outstanding_chapters_is_empty_without_all_chapters():
    ballot = _create_ballot(name="National Only Ballot", voters=["grand regent"])
    assert list(ballot.outstanding_chapters()) == []


@pytest.mark.django_db
def test_outstanding_chapters_excludes_candidate_and_inactive_chapters():
    ballot = _create_ballot(name="Chapter Outstanding Ballot", voters=["all_chapters"])
    # Explicit names: ChapterFactory draws randomly from the greek pool and
    # matches on name, so three unnamed chapters can collapse into one row.
    active = ChapterFactory.create(name="alpha")
    candidate = ChapterFactory.create(name="beta", candidate_chapter=True)
    inactive = ChapterFactory.create(name="chi", active=False)
    outstanding = list(ballot.outstanding_chapters())
    assert active in outstanding
    assert candidate not in outstanding
    assert inactive not in outstanding


# ---------------------------------------------------------------------------
# Ballot.outstanding_for_user (drives the nav badge / home page nudge)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_outstanding_for_user_lists_open_ballots_for_the_role():
    ballot = _create_ballot(name="Nudge Ballot", voters=["grand regent"])
    user = UserFactory.create()
    user.current_roles = ["grand regent"]
    user.save()
    assert list(Ballot.outstanding_for_user(user)) == [ballot]


@pytest.mark.django_db
def test_outstanding_for_user_skips_closed_ballots():
    _create_ballot(
        name="Closed Nudge Ballot",
        voters=["grand regent"],
        due_date=datetime.date.today() - datetime.timedelta(days=1),
    )
    user = UserFactory.create()
    user.current_roles = ["grand regent"]
    user.save()
    assert list(Ballot.outstanding_for_user(user)) == []


@pytest.mark.django_db
def test_outstanding_for_user_skips_ballots_already_voted():
    ballot = _create_ballot(name="Voted Nudge Ballot", voters=["grand regent"])
    user = UserFactory.create()
    user.current_roles = ["grand regent"]
    user.save()
    BallotComplete(ballot=ballot, user=user, motion="aye", role="grand regent").save()
    assert list(Ballot.outstanding_for_user(user)) == []


@pytest.mark.django_db
def test_outstanding_for_user_skips_a_ballot_the_chapter_already_voted():
    ballot = _create_ballot(name="Chapter Voted Nudge", voters=["all_chapters"])
    chapter = ChapterFactory.create()
    regent = UserFactory.create(chapter=chapter)
    BallotComplete(ballot=ballot, user=regent, motion="aye", role="regent").save()
    scribe = UserFactory.create(chapter=chapter)
    scribe.current_roles = ["scribe"]
    scribe.save()
    assert ballot not in Ballot.outstanding_for_user(scribe)


@pytest.mark.django_db
def test_outstanding_for_user_is_empty_without_a_role():
    _create_ballot(name="No Role Nudge Ballot", voters=["all_chapters"])
    user = UserFactory.create()
    assert list(Ballot.outstanding_for_user(user)) == []


@pytest.mark.django_db
def test_outstanding_for_user_is_empty_for_anonymous():
    assert list(Ballot.outstanding_for_user(AnonymousUser())) == []
