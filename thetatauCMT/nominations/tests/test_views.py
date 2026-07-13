"""VWI-2: the recommendation form as the viewflow Start view.

Exercises the actual Start view over HTTP (login -> POST -> process starts and
advances to nominee_consent) plus the form-level rules (multi-submission,
not-interested block, positions sourced from NAT_OFFICERS).
"""

import pytest
from django.urls import reverse
from django.utils import timezone
from viewflow.activation import STATUS
from viewflow.models import Task

from core.models import NAT_OFFICERS
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.forms import NOT_INTERESTED_MESSAGE, NominationForm
from thetatauCMT.nominations.models import Nomination
from thetatauCMT.nominations.tests.factories import NominationFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _start_url():
    # Resolved inside tests: reversing a viewflow frontend URL touches the DB,
    # which pytest-django forbids at module/collection time.
    return reverse("viewflow:nominations:nomination:start")


def _post_data(nominee, **overrides):
    data = {
        "nominee": nominee.pk,
        "level": "national",
        "reason": "Would be an excellent volunteer.",
        "recommended_positions": ["grand regent"],
        "discussed_with_nominee": "on",
        # viewflow start-view management form (ActivationDataForm, hidden).
        "_viewflow_activation-started": timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    data.update(overrides)
    return data


def _active_consent_task(nomination):
    return Task.objects.filter(
        process=nomination,
        flow_task=NominationFlow.nominee_consent,
        status__in=[STATUS.NEW, STATUS.ASSIGNED],
    ).first()


# ---------------------------------------------------------------------------
# The Start view is wired and renders the form
# ---------------------------------------------------------------------------
def test_start_view_get_renders_form(auto_login_user):
    client, _ = auto_login_user()
    response = client.get(_start_url(), follow=True)
    assert response.status_code == 200
    assert isinstance(response.context["form"], NominationForm)


# ---------------------------------------------------------------------------
# Acceptance: on submit the process starts and advances to nominee_consent
# ---------------------------------------------------------------------------
def test_post_starts_process_and_advances_to_consent(auto_login_user):
    client, nominator = auto_login_user()
    nominee = UserFactory.create()
    # A successful start redirects (302); we don't follow it because the next
    # task (nominee_consent) is owned by the nominee, not the nominator.
    response = client.post(_start_url(), _post_data(nominee))
    assert response.status_code == 302

    assert Nomination.objects.count() == 1
    nomination = Nomination.objects.get()
    assert nomination.nominator == nominator
    assert nomination.nominee == nominee
    assert "national" in nomination.level
    assert "grand regent" in nomination.recommended_positions
    assert nomination.discussed_with_nominee is True

    # The start task is done and the flow is waiting at nominee_consent.
    assert Task.objects.filter(process=nomination, flow_task=NominationFlow.start, status=STATUS.DONE).exists()
    assert _active_consent_task(nomination) is not None


# ---------------------------------------------------------------------------
# Acceptance: multiple submissions for the same person are allowed / retained
# ---------------------------------------------------------------------------
def test_multiple_submissions_allowed_for_same_nominee(auto_login_user):
    client, _ = auto_login_user()
    nominee = UserFactory.create()

    first = client.post(_start_url(), _post_data(nominee, reason="First rec"))
    second = client.post(_start_url(), _post_data(nominee, reason="Second rec"))
    assert first.status_code == 302
    assert second.status_code == 302

    nominations = Nomination.objects.filter(nominee=nominee)
    assert nominations.count() == 2
    # Both are independent processes, each waiting at nominee_consent.
    for nomination in nominations:
        assert _active_consent_task(nomination) is not None


def test_multiple_submissions_allowed_even_after_failed_vetting(auto_login_user):
    # A prior nomination that failed vetting (retained, not_interested is False)
    # must NOT block a fresh recommendation.
    client, _ = auto_login_user()
    nominee = UserFactory.create()
    NominationFactory.create(nominee=nominee, not_interested=False, vetting_passed=False)

    response = client.post(_start_url(), _post_data(nominee))
    assert response.status_code == 302
    assert Nomination.objects.filter(nominee=nominee).count() == 2


# ---------------------------------------------------------------------------
# Acceptance: submission blocked ONLY when the nominee declined (not_interested)
# ---------------------------------------------------------------------------
def test_post_blocked_when_nominee_not_interested(auto_login_user):
    client, _ = auto_login_user()
    nominee = UserFactory.create()
    NominationFactory.create(nominee=nominee, not_interested=True)

    # An invalid (blocked) submission re-renders the form with 200 -- no redirect.
    response = client.post(_start_url(), _post_data(nominee))
    assert response.status_code == 200
    # No new nomination process was started (only the pre-existing record).
    assert Nomination.objects.filter(nominee=nominee).count() == 1
    assert NOT_INTERESTED_MESSAGE in response.content.decode()


def test_form_block_message_is_exact():
    nominee = UserFactory.create()
    NominationFactory.create(nominee=nominee, not_interested=True)
    form = NominationForm(data={"nominee": nominee.pk, "level": "national", "reason": "x"})
    assert not form.is_valid()
    assert form.errors["__all__"] == [NOT_INTERESTED_MESSAGE]


# ---------------------------------------------------------------------------
# Acceptance: position choices are sourced from core.models.NAT_OFFICERS
# ---------------------------------------------------------------------------
def test_recommended_positions_choices_from_nat_officers():
    form = NominationForm()
    choice_values = [value for value, _label in form.fields["recommended_positions"].choices]
    assert set(choice_values) == set(NAT_OFFICERS)
    # A known council role and a national-officer role are both present.
    assert "grand regent" in choice_values
    assert "regional director" in choice_values
