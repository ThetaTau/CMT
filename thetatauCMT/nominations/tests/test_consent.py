"""VWI-3: tokenized (no-login) nominee consent.

Covers the token util (uniqueness/expiry/rotation), the consent email carrying
the token link, and the tokenized landing view (each choice routes the flow
correctly; interested captures preferences; not_interested sets the flag + note;
invalid/expired tokens are handled).
"""

import datetime
import uuid

import pytest
from django.urls import reverse
from django.utils import timezone
from viewflow.activation import STATUS
from viewflow.models import Task

from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.forms import NomineeConsentForm
from thetatauCMT.nominations.tests.factories import NominationFactory
from thetatauCMT.nominations.tokens import consent_link, get_nomination_by_token, issue_consent_token
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _start(**kwargs):
    """Start a NominationFlow programmatically.

    Runs ``send_consent_request`` (issues the token + emails the nominee) and
    leaves the process waiting at ``nominee_consent``.
    """
    activation = NominationFlow.start.activation_class()
    activation.initialize(NominationFlow.start, None)
    process = activation.process
    process.nominator = kwargs.pop("nominator", None) or UserFactory.create()
    process.nominee = kwargs.pop("nominee", None) if "nominee" in kwargs else UserFactory.create()
    process.nominee_name = kwargs.pop("nominee_name", "")
    process.nominee_email = kwargs.pop("nominee_email", "")
    process.reason = kwargs.pop("reason", "Would be great")
    process.recommended_positions = kwargs.pop("recommended_positions", ["grand regent"])
    for key, value in kwargs.items():
        setattr(process, key, value)
    activation.prepare()
    activation.done()
    if getattr(activation, "lock", None):
        activation.lock.__exit__(None, None, None)
    process.refresh_from_db()
    return process


def _consent_url(nomination):
    return reverse("nominations:consent", kwargs={"token": nomination.consent_token})


def _active(process, node):
    return Task.objects.filter(process=process, flow_task=node, status__in=[STATUS.NEW, STATUS.ASSIGNED]).first()


def _done(process, node):
    return Task.objects.filter(process=process, flow_task=node, status=STATUS.DONE).first()


def _email_text(email):
    parts = [email.subject, email.body or ""]
    parts += [content for content, _mime in getattr(email, "alternatives", [])]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Token: uniqueness, rotation, expiry, resolution
# ---------------------------------------------------------------------------
def test_tokens_are_unique_per_nomination():
    n1, n2 = NominationFactory.create(), NominationFactory.create()
    assert issue_consent_token(n1) != issue_consent_token(n2)
    assert n1.consent_token != n2.consent_token


def test_issue_token_rotates_and_sets_future_expiry():
    nomination = NominationFactory.create()
    old = nomination.consent_token
    new = issue_consent_token(nomination)
    assert new != old
    assert nomination.consent_token_expires > timezone.now()
    assert nomination.consent_token_expired is False


def test_token_expired_when_past_or_unset():
    nomination = NominationFactory.create()
    assert nomination.consent_token_expired is True  # never issued -> unusable
    issue_consent_token(nomination)
    nomination.consent_token_expires = timezone.now() - datetime.timedelta(days=1)
    assert nomination.consent_token_expired is True


def test_get_nomination_by_token_handles_invalid():
    assert get_nomination_by_token(uuid.uuid4()) is None
    assert get_nomination_by_token("not-a-uuid") is None
    assert get_nomination_by_token(None) is None
    nomination = NominationFactory.create()
    assert get_nomination_by_token(nomination.consent_token) == nomination


def test_consent_link_contains_token(settings):
    settings.CURRENT_URL = "https://cmt.thetatau.org"
    nomination = NominationFactory.create()
    issue_consent_token(nomination)
    link = consent_link(nomination)
    assert link.startswith("https://cmt.thetatau.org")
    assert str(nomination.consent_token) in link


# ---------------------------------------------------------------------------
# Email carries the tokenized link
# ---------------------------------------------------------------------------
def test_consent_email_sent_with_token_link(mailoutbox):
    nominee = UserFactory.create()
    process = _start(nominee=nominee)
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert nominee.email in email.to
    assert str(process.consent_token) in _email_text(email)


def test_consent_email_to_non_member_uses_supplied_email(mailoutbox):
    _ = _start(nominee=None, nominee_name="Nonmember Nita", nominee_email="nita@example.com")
    assert len(mailoutbox) == 1
    assert "nita@example.com" in mailoutbox[0].to


# ---------------------------------------------------------------------------
# Landing view: GET renders the form, invalid/expired/responded handled
# ---------------------------------------------------------------------------
def test_get_renders_consent_form(client):
    process = _start()
    response = client.get(_consent_url(process))
    assert response.status_code == 200
    assert isinstance(response.context["form"], NomineeConsentForm)


def test_invalid_token_is_handled(client):
    url = reverse("nominations:consent", kwargs={"token": uuid.uuid4()})
    response = client.get(url)
    assert response.status_code == 200
    assert "not valid" in response.content.decode().lower()


def test_expired_token_is_handled(client):
    process = _start()
    process.consent_token_expires = timezone.now() - datetime.timedelta(days=1)
    process.save(update_fields=["consent_token_expires"])
    response = client.get(_consent_url(process))
    assert response.status_code == 200
    assert "expired" in response.content.decode().lower()
    # The flow has NOT advanced.
    assert _active(process, NominationFlow.nominee_consent) is not None


def test_post_with_expired_token_does_not_advance(client):
    process = _start()
    process.consent_token_expires = timezone.now() - datetime.timedelta(days=1)
    process.save(update_fields=["consent_token_expires"])
    response = client.post(_consent_url(process), {"response": "interested"})
    assert response.status_code == 200
    process.refresh_from_db()
    assert process.consent_status == "pending"
    assert _active(process, NominationFlow.nominee_consent) is not None


def test_already_responded_is_handled(client):
    process = _start()
    client.post(_consent_url(process), {"response": "interested"})
    response = client.get(_consent_url(process))
    assert response.status_code == 200
    assert "already responded" in response.content.decode().lower()


# ---------------------------------------------------------------------------
# Each choice routes the flow correctly
# ---------------------------------------------------------------------------
def test_interested_routes_to_vetting_and_captures_preferences(client):
    process = _start()
    response = client.post(
        _consent_url(process),
        {
            "response": "interested",
            "interested_positions": ["grand regent", "grand scribe"],
            "interested_level": "regional",
            "note": "Excited to help",
        },
    )
    assert response.status_code == 200
    process.refresh_from_db()
    assert process.consent_status == "interested"
    assert set(process.interested_positions) == {"grand regent", "grand scribe"}
    assert "regional" in process.interested_level
    assert process.consent_notes == "Excited to help"
    # Consent completed -> vetting is now the waiting task.
    assert _active(process, NominationFlow.nominee_consent) is None
    assert _active(process, NominationFlow.vetting) is not None


def test_follow_up_later_parks_awaiting_follow_up(client):
    process = _start()
    response = client.post(_consent_url(process), {"response": "follow_up_later", "note": "Busy now"})
    assert response.status_code == 200
    process.refresh_from_db()
    assert process.consent_status == "follow_up_later"
    assert process.not_interested is False
    assert _active(process, NominationFlow.vetting) is None
    # Parked awaiting follow-up (not ended).
    assert _active(process, NominationFlow.follow_up_wait) is not None
    assert process.finished is None


def test_not_interested_sets_flag_note_and_closes(client):
    process = _start()
    response = client.post(_consent_url(process), {"response": "not_interested", "note": "Not at this time"})
    assert response.status_code == 200
    process.refresh_from_db()
    assert process.consent_status == "not_interested"
    assert process.not_interested is True
    assert process.consent_notes == "Not at this time"
    assert _active(process, NominationFlow.vetting) is None
    assert _done(process, NominationFlow.closed) is not None
    assert process.finished is not None
