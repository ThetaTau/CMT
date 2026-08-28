"""Tests for the outstanding-ballot nav badge and home page nudge."""

import datetime
from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.ballots.models import Ballot, BallotComplete


def _create_ballot(**kwargs):
    defaults = dict(
        name=f"Nudge Ballot {datetime.datetime.now().microsecond}",
        type="other",
        description="A test ballot description",
        due_date=datetime.date.today() + timedelta(days=30),
        voters=["all_chapters"],
    )
    defaults.update(kwargs)
    ballot = Ballot(**defaults)
    ballot.save()
    return ballot


def _make_officer(user, client):
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


@pytest.mark.django_db
def test_nav_shows_a_ballot_badge_when_a_vote_is_outstanding(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot()
    response = client.get(reverse("home"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'id="outstanding-ballots"' in body
    assert ballot.name in body


@pytest.mark.django_db
def test_nav_has_no_ballot_badge_without_an_outstanding_vote(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    ballot = _create_ballot()
    BallotComplete(ballot=ballot, user=user, motion="aye", role="regent").save()
    response = client.get(reverse("home"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'id="outstanding-ballots"' not in body
    assert ballot.name not in body


@pytest.mark.django_db
def test_nav_has_no_ballot_badge_for_a_member_without_a_role(auto_login_user):
    client, user = auto_login_user()
    _create_ballot()
    response = client.get(reverse("home"))
    assert response.status_code == 200
    assert 'id="outstanding-ballots"' not in response.content.decode("utf-8")


@pytest.mark.django_db
def test_home_nudge_appears_above_the_announcements_heading(auto_login_user):
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    _create_ballot()
    body = client.get(reverse("home")).content.decode("utf-8")
    assert body.index("waiting on your vote") < body.index("<h1>Announcements</h1>")
