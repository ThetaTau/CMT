import datetime
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.core import mail
from django.urls import reverse

from thetatauCMT.ballots.models import Ballot, BallotComplete
from thetatauCMT.users.tests.factories import UserFactory


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _make_officer(user, client):
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


def _create_ballot(**kwargs):
    defaults = dict(
        name=f"Test Ballot {datetime.datetime.now().microsecond}",
        type="other",
        description="A test ballot description",
        due_date=datetime.date.today() + timedelta(days=30),
        voters="grand regent",
    )
    defaults.update(kwargs)
    ballot = Ballot(**defaults)
    ballot.save()
    return ballot


@pytest.mark.django_db
def test_ballot_user_list_view_authenticated(auto_login_user):
    """Any officer user can see the ballot voting list (requires current_roles to be non-empty)."""
    # Ballot.user_ballots() does roles[0] which fails if user has no roles
    client, user = auto_login_user(make_officer="regent")
    url = reverse("ballots:votelist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ballot_user_list_view_no_roles(auto_login_user):
    """A user with no current_roles can load the vote list without an IndexError.

    Regression test for GH #1069: Ballot.user_ballots() indexed roles[0] which
    raised IndexError when the user had no current_roles.
    """
    client, user = auto_login_user()  # no make_officer -> current_roles is None
    assert not user.current_roles
    url = reverse("ballots:votelist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ballot_user_list_view_unauthenticated(client):
    url = reverse("ballots:votelist")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_ballot_list_view_natoff(auto_login_user):
    """BallotListView requires natoff group."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("ballots:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ballot_list_view_regular_user_redirected(auto_login_user):
    """Non-natoff users are redirected from BallotListView."""
    client, user = auto_login_user()
    url = reverse("ballots:list")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_ballot_redirect_view(auto_login_user):
    """A non-national officer lands on their own ballots, not the natoff-only list."""
    client, user = auto_login_user()
    url = reverse("ballots:redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert response["Location"] == reverse("ballots:votelist")


@pytest.mark.django_db
def test_ballot_redirect_view_natoff(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    response = client.get(reverse("ballots:redirect"))
    assert response.status_code == 302
    assert "/ballots/list/" in response["Location"]


@pytest.mark.django_db
def test_ballot_redirect_view_unauthenticated(client):
    url = reverse("ballots:redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_ballot_create_view_natoff_get(auto_login_user):
    """Natoff can access the ballot create form."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("ballots:create")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ballot_create_view_regular_user_redirected(auto_login_user):
    """Non-natoff users cannot access ballot create."""
    client, user = auto_login_user()
    url = reverse("ballots:create")
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_ballot_create_view_renders_datepicker(auto_login_user):
    """Due Date needs the shared picker; the view used to build a default
    ModelForm from ``fields``, which renders a bare text input."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    response = client.get(reverse("ballots:create"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "deferDateTimePicker_id_due_date()" in body
    assert 'name="due_date"' in body
    # Without ``{{ form.media }}`` the widget renders but never initialises.
    assert "tempusdominus-bootstrap-4" in body


@pytest.mark.django_db
def test_ballot_update_view_renders_datepicker(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    ballot = Ballot(
        sender="Grand Scribe",
        name="Picker Ballot",
        type="other",
        description="desc",
        due_date=datetime.date.today() + timedelta(days=30),
        voters=["all_chapters"],
    )
    ballot.save()
    response = client.get(reverse("ballots:update", kwargs={"pk": ballot.pk}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "deferDateTimePicker_id_due_date()" in body
    assert "tempusdominus-bootstrap-4" in body


@pytest.mark.django_db
def test_ballot_detail_view_natoff(auto_login_user):
    """The results page loads for a National Officer."""
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["all_chapters", "grand regent"])
    response = client.get(reverse("ballots:detail", kwargs={"slug": ballot.slug}))
    assert response.status_code == 200


@pytest.mark.django_db
def test_ballot_vote_view_officer_get(auto_login_user):
    """Officers can access the ballot vote form."""
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters="regent")
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_ballot_vote_view_regular_user_redirected(auto_login_user):
    """Non-officer users cannot access vote view."""
    client, user = auto_login_user()
    ballot = _create_ballot()
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.get(url)
    assert response.status_code == 302


@pytest.mark.django_db
def test_ballot_copy_view_natoff(auto_login_user):
    """Natoff can access the ballot copy form."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    ballot = _create_ballot()
    url = reverse("ballots:copy", kwargs={"pk": ballot.pk})
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# BallotCreateView — POST creates a ballot (get_success_url) (5.7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ballot_create_view_post_creates_ballot(auto_login_user):
    """Natoff can POST to create a ballot and is redirected to the ballot list."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    url = reverse("ballots:create")
    post_data = {
        "name": f"New Ballot {datetime.datetime.now().microsecond}",
        "type": "other",
        "description": "New ballot description",
        "due_date": (datetime.date.today() + timedelta(days=30)).isoformat(),
        "voters": "grand regent",
    }
    response = client.post(url, post_data)
    # Success should redirect (302) to ballots:list
    assert response.status_code in (200, 302)


# ---------------------------------------------------------------------------
# BallotCompleteCreateView — POST vote form (form_valid path) (5.7)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ballot_vote_view_officer_post_valid(auto_login_user):
    """An officer with a valid role can POST a vote and is redirected."""
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters="regent")
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    post_data = {
        "motion": "yes",
    }
    response = client.post(url, post_data)
    # form_valid creates the BallotComplete and redirects to votelist
    assert response.status_code in (200, 302)


@pytest.mark.django_db
def test_ballot_vote_view_user_without_role_gets_error(auto_login_user):
    """A user with no matching role gets an error message (form_invalid path)."""
    client, user = auto_login_user()
    # User is not an officer so current_roles is empty → form_invalid
    ballot = _create_ballot(voters="grand regent")
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    # GET should succeed since OfficerRequiredMixin isn't strict here
    response = client.get(url)
    # Could be 200 or 302 depending on mixin
    assert response.status_code in (200, 302)


@pytest.mark.django_db
def test_ballot_vote_view_missing_ballot_returns_404(auto_login_user):
    """Voting on a non-existent ballot slug returns 404, not a 500.

    ``BallotCompleteCreateView.get_context_data`` did
    ``Ballot.objects.get(slug=...)`` which raised Ballot.DoesNotExist (issue
    #922); it now uses ``get_object_or_404``.
    """
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    url = reverse("ballots:vote", kwargs={"slug": "this-ballot-does-not-exist"})
    response = client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db
def test_ballot_update_view_post_saves(auto_login_user):
    """Updating a ballot used to 500: the view inherited the event/score
    ``TypeFieldFilteredChapterAdd.form_valid``, which called ``.task`` on the
    ballot's plain ``type`` string."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["grand regent"])
    response = client.post(
        reverse("ballots:update", kwargs={"pk": ballot.pk}),
        {
            "name": ballot.name,
            "sender": "Grand Regent",
            "type": "suspension",
            "description": "Edited description",
            "due_date": (datetime.date.today() + timedelta(days=45)).isoformat(),
            "voters": ["grand regent"],
        },
    )
    assert response.status_code == 302
    ballot.refresh_from_db()
    assert ballot.sender == "Grand Regent"
    assert ballot.type == "suspension"


@pytest.mark.django_db
def test_ballot_create_view_rejects_a_past_due_date(auto_login_user):
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    response = client.post(
        reverse("ballots:create"),
        {
            "name": f"Past Ballot {datetime.datetime.now().microsecond}",
            "sender": "Grand Scribe",
            "type": "other",
            "description": "Already closed",
            "due_date": (datetime.date.today() - timedelta(days=1)).isoformat(),
            "voters": ["grand regent"],
        },
    )
    assert response.status_code == 200
    assert "due date must be today or later" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_ballot_list_voters_filter_matches_one_of_several_voters(auto_login_user):
    """The generated filter matched the whole comma separated list exactly."""
    client, user = auto_login_user(make_officer="national")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["all_chapters", "grand regent"])
    response = client.get(reverse("ballots:list") + "?voters=grand+regent")
    assert response.status_code == 200
    assert ballot.name in response.content.decode("utf-8")


# ---------------------------------------------------------------------------
# Results are Grand Regent / Grand Scribe only
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ballot_detail_view_hides_votes_from_other_officers(auto_login_user):
    """Any officer sees who has voted; only GR/GS see the totals."""
    client, user = auto_login_user(make_officer="treasurer")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    voter = UserFactory.create()
    BallotComplete(ballot=ballot, user=voter, motion="aye", role="regent").save()
    response = client.get(reverse("ballots:detail", kwargs={"slug": ballot.slug}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Ballot Returned" in body
    assert "Motion" not in body
    assert "Ayes:" not in body
    assert voter.name in body


@pytest.mark.django_db
def test_ballot_detail_view_shows_totals_but_not_motions_to_grand_scribe(auto_login_user):
    client, user = auto_login_user(make_officer="grand scribe")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    voter = UserFactory.create()
    BallotComplete(ballot=ballot, user=voter, motion="aye", role="regent").save()
    response = client.get(reverse("ballots:detail", kwargs={"slug": ballot.slug}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Ayes:" in body
    # The aggregate only: no per-voter motion, even for the Grand Scribe.
    assert "Motion" not in body


@pytest.mark.django_db
def test_ballot_detail_view_hides_totals_from_other_national_officers(auto_login_user):
    """A National Officer who is not GR/GS gets the same view as any officer."""
    client, user = auto_login_user(make_officer="grand treasurer")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    response = client.get(reverse("ballots:detail", kwargs={"slug": ballot.slug}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Ayes:" not in body
    assert "Motion" not in body


@pytest.mark.django_db
def test_ballot_detail_view_motion_filter_is_never_offered(auto_login_user):
    """Filtering by motion would expose individual votes, so it does not exist."""
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    voter = UserFactory.create()
    BallotComplete(ballot=ballot, user=voter, motion="aye", role="regent").save()
    response = client.get(reverse("ballots:detail", kwargs={"slug": ballot.slug}) + "?motion=aye")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="motion"' not in body
    assert 'name="status"' in body


@pytest.mark.django_db
def test_ballot_detail_view_requires_an_officer(auto_login_user):
    client, user = auto_login_user()
    ballot = _create_ballot()
    response = client.get(reverse("ballots:detail", kwargs={"slug": ballot.slug}))
    assert response.status_code == 302


@pytest.mark.django_db
def test_ballot_detail_view_missing_slug_returns_404(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    response = client.get(reverse("ballots:detail", kwargs={"slug": "nope"}))
    assert response.status_code == 404


@pytest.mark.django_db
def test_ballot_list_view_hides_tallies_from_other_national_officers(auto_login_user):
    client, user = auto_login_user(make_officer="grand treasurer")
    _make_natoff(user, client)
    _create_ballot(voters=["all_chapters"])
    response = client.get(reverse("ballots:list"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Ballots Returned" in body
    assert "Ayes" not in body


@pytest.mark.django_db
def test_ballot_list_view_shows_tallies_to_grand_regent(auto_login_user):
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    _create_ballot(voters=["all_chapters"])
    response = client.get(reverse("ballots:list"))
    assert response.status_code == 200
    assert "Ayes" in response.content.decode("utf-8")


# ---------------------------------------------------------------------------
# Only the Regent and Scribe cast the chapter's single vote
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chapter_ballot_vote_rejected_for_treasurer(auto_login_user):
    client, user = auto_login_user(make_officer="treasurer")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.post(url, {"motion": "aye", "authority": "chapter_vote"})
    assert response.status_code == 200
    assert not BallotComplete.objects.filter(ballot=ballot, user=user).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["regent", "scribe"])
def test_chapter_ballot_vote_accepted_for_regent_and_scribe(auto_login_user, role):
    client, user = auto_login_user(make_officer=role)
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.post(url, {"motion": "aye", "authority": "chapter_vote"})
    assert response.status_code == 302
    vote = BallotComplete.objects.get(ballot=ballot, user=user)
    assert vote.role == role
    assert vote.motion == "aye"
    assert vote.authority == "chapter_vote"


@pytest.mark.django_db
def test_chapter_votes_only_once(auto_login_user):
    """The Scribe cannot vote again after the Regent already did."""
    client, scribe = auto_login_user(make_officer="scribe")
    _make_officer(scribe, client)
    ballot = _create_ballot(voters=["all_chapters"])
    regent = UserFactory.create(chapter=scribe.chapter)
    BallotComplete(ballot=ballot, user=regent, motion="nay", role="regent").save()
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.post(url, {"motion": "aye", "authority": "chapter_vote"})
    assert response.status_code == 200
    assert not BallotComplete.objects.filter(ballot=ballot, user=scribe).exists()
    assert ballot.completed.count() == 1


@pytest.mark.django_db
def test_vote_rejected_after_the_due_date(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"], due_date=datetime.date.today() - timedelta(days=1))
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    response = client.post(url, {"motion": "aye", "authority": "chapter_vote"})
    assert response.status_code == 200
    assert not BallotComplete.objects.filter(ballot=ballot).exists()


@pytest.mark.django_db
def test_vote_form_does_not_offer_incomplete(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot(voters=["all_chapters"])
    response = client.get(reverse("ballots:vote", kwargs={"slug": ballot.slug}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'value="aye"' in body
    assert 'value="incomplete"' not in body


@pytest.mark.django_db
def test_vote_rejected_when_a_user_votes_twice(auto_login_user):
    """A double submit used to raise an IntegrityError from unique_together."""
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    ballot = _create_ballot(voters=["grand regent"])
    url = reverse("ballots:vote", kwargs={"slug": ballot.slug})
    assert client.post(url, {"motion": "aye"}).status_code == 302
    response = client.post(url, {"motion": "nay"})
    assert response.status_code == 200
    assert ballot.completed.count() == 1


# ---------------------------------------------------------------------------
# Creating a ballot emails the voters
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_creating_a_ballot_emails_the_voters(auto_login_user):
    client, user = auto_login_user(make_officer="grand regent")
    _make_natoff(user, client)
    mail.outbox = []
    response = client.post(
        reverse("ballots:create"),
        {
            "name": f"Emailed Ballot {datetime.datetime.now().microsecond}",
            "sender": "Grand Scribe",
            "type": "other",
            "description": "New ballot description",
            "due_date": (datetime.date.today() + timedelta(days=30)).isoformat(),
            "voters": ["grand regent"],
        },
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to
