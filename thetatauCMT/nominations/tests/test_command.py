"""VWI-11: daily follow-up management command."""

import datetime
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.models import Nomination
from thetatauCMT.nominations.services import has_active_consent_task

from ._flow_helpers import advance_to, complete_view, start_nomination

pytestmark = pytest.mark.django_db


def _run(**kwargs):
    out = StringIO()
    call_command("nomination_follow_up", stdout=out, **kwargs)
    return out.getvalue()


def _set_contacted(process, days_ago):
    Nomination.objects.filter(pk=process.pk).update(last_contacted=timezone.now() - datetime.timedelta(days=days_ago))
    process.refresh_from_db()


def _to_follow_up(process):
    complete_view(process, NominationFlow.nominee_consent, consent_status="follow_up_later")


def _recent(process):
    process.refresh_from_db()
    return process.last_contacted and process.last_contacted > timezone.now() - datetime.timedelta(hours=1)


# --- Fires at >= interval ---------------------------------------------------
def test_fires_for_stale_awaiting_response(mailoutbox):
    process = start_nomination()  # parked at nominee_consent
    _set_contacted(process, 200)
    mailoutbox.clear()
    _run()
    assert len(mailoutbox) >= 1
    assert has_active_consent_task(process) is True  # still awaiting
    assert _recent(process)  # last_contacted refreshed


def test_fires_for_stale_follow_up(mailoutbox):
    process = start_nomination()
    _to_follow_up(process)
    _set_contacted(process, 200)
    mailoutbox.clear()
    _run()
    assert len(mailoutbox) >= 1
    # Re-contact returned it to awaiting the nominee's response.
    assert has_active_consent_task(process) is True
    assert _recent(process)


# --- Does not fire before interval -----------------------------------------
def test_does_not_fire_before_interval(mailoutbox):
    process = start_nomination()
    _set_contacted(process, 100)  # < ~180 days
    mailoutbox.clear()
    _run()
    assert len(mailoutbox) == 0
    process.refresh_from_db()
    assert process.last_contacted < timezone.now() - datetime.timedelta(days=90)


# --- Re-fires next interval + idempotent within a run ----------------------
def test_refires_next_interval_and_idempotent(mailoutbox):
    process = start_nomination()
    _set_contacted(process, 200)

    mailoutbox.clear()
    _run()
    assert len(mailoutbox) >= 1
    assert _recent(process)

    # Running again immediately does nothing (idempotent; not yet due).
    mailoutbox.clear()
    _run()
    assert len(mailoutbox) == 0

    # After another interval, it re-fires.
    _set_contacted(process, 200)
    mailoutbox.clear()
    _run()
    assert len(mailoutbox) >= 1


# --- Skips nominations that moved on / not_interested ----------------------
def test_skips_nominations_that_moved_on(mailoutbox):
    process = start_nomination()
    advance_to(process, "vetting")  # now at vetting, not consent/follow-up
    _set_contacted(process, 200)
    mailoutbox.clear()
    _run()
    assert len(mailoutbox) == 0


def test_skips_not_interested(mailoutbox):
    process = start_nomination()
    complete_view(process, NominationFlow.nominee_consent, consent_status="not_interested")
    _set_contacted(process, 200)
    mailoutbox.clear()
    _run()
    assert len(mailoutbox) == 0


# --- Interval from config + flags ------------------------------------------
def test_interval_read_from_config(mailoutbox):
    Config.objects.create(key="follow_up_interval_months", value="1", description="i")
    process = start_nomination()
    _set_contacted(process, 45)  # > 30 days (1 month)
    mailoutbox.clear()
    _run()
    assert len(mailoutbox) >= 1


def test_dry_run_reports_without_sending(mailoutbox):
    process = start_nomination()
    _set_contacted(process, 200)
    mailoutbox.clear()
    output = _run(dry_run=True)
    assert len(mailoutbox) == 0
    assert "dry-run" in output.lower()
    process.refresh_from_db()
    assert process.last_contacted < timezone.now() - datetime.timedelta(days=90)


def test_interval_months_flag_override(mailoutbox):
    process = start_nomination()
    _set_contacted(process, 45)
    mailoutbox.clear()
    _run(interval_months=1)  # 1 month -> 45 days is due
    assert len(mailoutbox) >= 1
