"""The vote itself must not be reachable through admin tooling.

A ballot is secret: only the voter sees their own vote, and only the Grand
Regent and Grand Scribe see the aggregate counts. That has to hold in the
Django admin and the report builder too, not just in the member-facing views.
"""

import datetime
from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib import admin
from django.test import override_settings
from django.urls import reverse

from thetatauCMT.ballots.admin import BallotCompleteAdmin, BallotCompleteInline
from thetatauCMT.ballots.models import Ballot, BallotComplete
from thetatauCMT.users.tests.factories import UserFactory


def _create_ballot(**kwargs):
    defaults = dict(
        name=f"Admin Ballot {datetime.datetime.now().microsecond}",
        type="other",
        description="A test ballot description",
        due_date=datetime.date.today() + timedelta(days=30),
        voters=["all_chapters"],
    )
    defaults.update(kwargs)
    ballot = Ballot(**defaults)
    ballot.save()
    return ballot


@pytest.fixture
def signed_admin_client(admin_client, admin_user):
    """pytest-django's admin client, with the RMP ``RMPSignMiddleware`` demands."""
    from thetatauCMT.forms.models import RiskManagement

    RiskManagement.objects.get_or_create(
        user=admin_user,
        defaults=dict(
            role="regent",
            submission=None,
            date=datetime.date.today(),
            alcohol=False,
            hosting=False,
            monitoring=False,
            member=False,
            officer=False,
            abusive=False,
            hazing=False,
            substances=False,
            high_risk=False,
            transportation=False,
            property_management=False,
            guns=False,
            trademark=False,
            social=False,
            indemnification=False,
            agreement=False,
            electronic_agreement=False,
            terms_agreement=False,
            typed_name="test admin",
        ),
    )
    return admin_client


def test_admin_never_lists_the_motion():
    assert "motion" not in BallotCompleteAdmin.list_display
    assert "motion" not in BallotCompleteAdmin.list_filter
    assert "motion" in BallotCompleteAdmin.exclude
    assert "motion" not in BallotCompleteInline.fields


@pytest.mark.django_db
@override_settings(DEBUG=True)  # superusers bypass RequireSuperuser2FAMiddleware only when DEBUG
def test_admin_change_form_does_not_render_the_motion(signed_admin_client):
    ballot = _create_ballot()
    voter = UserFactory.create()
    vote = BallotComplete(ballot=ballot, user=voter, motion="aye", role="regent")
    vote.save()
    url = reverse("admin:ballots_ballotcomplete_change", args=[vote.pk])
    response = signed_admin_client.get(url)
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="motion"' not in body
    assert "Aye" not in body


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_changelist_does_not_render_the_motion(signed_admin_client):
    ballot = _create_ballot()
    voter = UserFactory.create()
    BallotComplete(ballot=ballot, user=voter, motion="aye", role="regent").save()
    response = signed_admin_client.get(reverse("admin:ballots_ballotcomplete_changelist"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Aye" not in body
    assert voter.name in body


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_ballot_change_form_does_not_render_inline_motions(signed_admin_client):
    ballot = _create_ballot()
    voter = UserFactory.create()
    BallotComplete(ballot=ballot, user=voter, motion="abstain", role="regent").save()
    response = signed_admin_client.get(reverse("admin:ballots_ballot_change", args=[ballot.pk]))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="completed-0-motion"' not in body
    assert "Abstain" not in body


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_admin_cannot_add_a_vote_by_hand(signed_admin_client):
    response = signed_admin_client.get(reverse("admin:ballots_ballotcomplete_add"))
    assert response.status_code in (302, 403)


def test_report_builder_cannot_reach_the_vote_rows():
    assert "ballots.ballotcomplete" in settings.REPORT_BUILDER_EXCLUDE


def test_ballot_complete_is_registered_with_the_hardened_admin():
    assert isinstance(admin.site._registry[BallotComplete], BallotCompleteAdmin)
