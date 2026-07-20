"""VWI-4: not-interested block enforcement + follow-up / re-contact handling.

Covers the ``last_activity`` / ``last_contacted`` timestamps and the
``recontact_nomination`` hook the daily follow-up command (VWI-12) will call:
re-issuing the consent token + email and returning the process to awaiting the
nominee's response.
"""

import datetime

import pytest
from django.utils import timezone
from viewflow.activation import STATUS
from viewflow.models import Task

from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.forms import NOT_INTERESTED_MESSAGE, NominationForm
from thetatauCMT.nominations.models import Nomination
from thetatauCMT.nominations.services import (
    has_active_consent_task,
    is_awaiting_follow_up,
    nominations_awaiting_follow_up,
    recontact_nomination,
)
from thetatauCMT.nominations.tests.factories import NominationFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _start(**kwargs):
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


def _complete_consent(process, **updates):
    task = Task.objects.filter(
        process=process,
        flow_task=NominationFlow.nominee_consent,
        status__in=[STATUS.NEW, STATUS.ASSIGNED],
    ).first()
    for key, value in updates.items():
        setattr(process, key, value)
    process.save()
    activation = task.activate()
    if task.status == STATUS.NEW:
        activation.assign()
    activation.prepare()
    activation.done()


def _to_follow_up(process):
    _complete_consent(process, consent_status="follow_up_later")
    process.refresh_from_db()


def _email_text(email):
    parts = [email.subject, email.body or ""]
    parts += [content for content, _mime in getattr(email, "alternatives", [])]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# not_interested blocks NEW submissions (standard message)
# ---------------------------------------------------------------------------
def test_not_interested_blocks_new_submission():
    nominee = UserFactory.create()
    NominationFactory.create(nominee=nominee, not_interested=True)
    form = NominationForm(data={"nominee": nominee.pk, "level": ["national"], "reason": "x"})
    assert not form.is_valid()
    assert form.errors["__all__"] == [NOT_INTERESTED_MESSAGE]


def test_not_interested_only_blocks_that_nominee():
    declined = UserFactory.create()
    NominationFactory.create(nominee=declined, not_interested=True)
    other = UserFactory.create()
    form = NominationForm(data={"nominee": other.pk, "level": ["national"], "reason": "x"})
    assert form.is_valid(), form.errors


# ---------------------------------------------------------------------------
# Follow-up marks awaiting state + records timestamps
# ---------------------------------------------------------------------------
def test_initial_contact_stamps_timestamps():
    process = _start()
    assert process.last_contacted is not None
    assert process.last_activity is not None


def test_follow_up_later_marks_awaiting_and_stamps_activity():
    process = _start()
    marker = timezone.now()
    _to_follow_up(process)
    assert is_awaiting_follow_up(process) is True
    assert has_active_consent_task(process) is False
    assert process.consent_status == "follow_up_later"
    assert process.last_activity is not None and process.last_activity >= marker
    assert process.finished is None


# ---------------------------------------------------------------------------
# Re-contact hook: reissues token + email, returns to awaiting response
# ---------------------------------------------------------------------------
def test_recontact_reissues_token_and_email(mailoutbox):
    process = _start()
    old_token = process.consent_token
    old_contacted = process.last_contacted
    _to_follow_up(process)
    mailoutbox.clear()

    assert recontact_nomination(process) is True
    process.refresh_from_db()
    assert process.consent_token != old_token
    assert process.last_contacted > old_contacted
    assert len(mailoutbox) == 1
    assert str(process.consent_token) in _email_text(mailoutbox[0])


def test_recontact_returns_to_awaiting_response():
    process = _start()
    _to_follow_up(process)
    assert is_awaiting_follow_up(process) is True
    assert has_active_consent_task(process) is False

    recontact_nomination(process)
    process.refresh_from_db()
    # Returned to awaiting the nominee's response; no longer parked.
    assert has_active_consent_task(process) is True
    assert is_awaiting_follow_up(process) is False
    assert process.finished is None


def test_recontact_is_noop_when_not_awaiting_follow_up():
    process = _start()  # waiting at nominee_consent, not parked for follow-up
    assert recontact_nomination(process) is False


def test_recontact_can_repeat_every_cycle(mailoutbox):
    process = _start()
    _to_follow_up(process)
    recontact_nomination(process)
    process.refresh_from_db()
    # The nominee again asks to follow up later.
    _to_follow_up(process)
    assert is_awaiting_follow_up(process) is True
    token_before = process.consent_token
    mailoutbox.clear()

    assert recontact_nomination(process) is True
    process.refresh_from_db()
    assert process.consent_token != token_before
    assert len(mailoutbox) == 1
    assert has_active_consent_task(process) is True


# ---------------------------------------------------------------------------
# Query used by the daily follow-up command (VWI-12)
# ---------------------------------------------------------------------------
def test_nominations_awaiting_follow_up_lists_only_parked():
    parked = _start()
    _to_follow_up(parked)
    awaiting_consent = _start()  # still at nominee_consent
    result = nominations_awaiting_follow_up()
    assert parked in result
    assert awaiting_consent not in result


def test_nominations_awaiting_follow_up_respects_before_cutoff():
    stale = _start()
    _to_follow_up(stale)
    Nomination.objects.filter(pk=stale.pk).update(last_contacted=timezone.now() - datetime.timedelta(days=210))
    recent = _start()
    _to_follow_up(recent)

    cutoff = timezone.now() - datetime.timedelta(days=180)
    due = nominations_awaiting_follow_up(before=cutoff)
    assert stale in due
    assert recent not in due
