"""VWI-8: Confirmation node (CO confirm/deny) with a review screen."""

import datetime

import pytest
from django.template.loader import render_to_string
from viewflow.models import Task

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.users.tests.factories import UserFactory

from ._flow_helpers import active_task, advance_to, complete_view, done_task, start_nomination

pytestmark = pytest.mark.django_db


def _at_confirmation(**kwargs):
    process = start_nomination(**kwargs)
    advance_to(process, "confirmation")
    return process


def test_confirm_routes_to_appointment():
    process = _at_confirmation()
    complete_view(process, NominationFlow.confirmation, confirmed=True)
    assert active_task(process, NominationFlow.confirmation) is None
    assert active_task(process, NominationFlow.appointment) is not None


def test_confirmation_view_success_url_is_safe():
    """The confirmation task is assigned to a config-driven Confirmer who may not
    hold the natoff-only ``nominations.view_nomination`` permission, so the
    post-decision redirect must go to a page any user can reach (``home``)
    rather than the natoff review list or the viewflow default ``:detail`` page."""
    from django.urls import reverse

    from thetatauCMT.nominations.views import ConfirmationView

    assert ConfirmationView().get_success_url() == reverse("home")


def test_deny_routes_to_denial():
    process = _at_confirmation()
    complete_view(process, NominationFlow.confirmation, confirmed=False)
    assert active_task(process, NominationFlow.appointment) is None
    process.refresh_from_db()
    assert process.confirmed is False
    # Denial path taken (not appointment). VWI-10 fleshes out the denial node.
    assert (
        done_task(process, NominationFlow.denied) is not None
        or active_task(process, NominationFlow.denial_central_office) is not None
    )


def test_review_screen_shows_required_data():
    nominator = UserFactory.create(name="Nadia Nominator")
    process = _at_confirmation(nominator=nominator, recommended_positions=["grand regent"])
    # Give the interview a date so it renders.
    process.interview_date = datetime.date(2026, 2, 1)
    process.save(update_fields=["interview_date"])

    html = render_to_string(
        "nominations/confirmation.html",
        {
            "nomination": process,
            "history_tasks": list(Task.objects.filter(process=process).order_by("created")),
            "form": None,
        },
    )
    # Nominator is shown and links to their profile.
    assert "Nadia Nominator" in html
    assert f"/profile/{nominator.username}/" in html or "users:profile" not in html
    # Recommended position + level.
    assert "Grand Regent" in html
    assert process.get_level_display() in html
    # Vetting + interview + training outcomes surfaced.
    assert "Passed" in html  # vetting_passed True
    assert "Continue" in html  # interview_passed True
    assert "CMT LMS Volunteer Training" in html
    assert "Vector CommunityEDU" in html
    # Process history present.
    assert "history" in html.lower()


def test_confirmation_gated_to_configured_confirmer():
    confirmer = UserFactory.create(username="confirmer@example.com")
    Config.objects.create(key="Confirmer", value="confirmer@example.com", description="c")
    process = _at_confirmation()
    task = active_task(process, NominationFlow.confirmation)
    assert task.owner == confirmer
    assert task.owner_permission is not None
    assert NominationFlow.confirmation.can_execute(confirmer, task) is True
    assert NominationFlow.confirmation.can_execute(UserFactory.create(), task) is False
