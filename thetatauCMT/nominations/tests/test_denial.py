"""VWI-10: Rejection and denial handling."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from thetatauCMT.configs.models import Config
from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.forms import NominationForm
from thetatauCMT.nominations.models import Nomination
from thetatauCMT.users.tests.factories import UserFactory

from ._flow_helpers import active_task, advance_to, complete_view, done_task, start_nomination

pytestmark = pytest.mark.django_db


# --- Vetting / interview failure: thank-you + close, retain, no not_interested
def test_vetting_failure_sends_thank_you_and_retains(mailoutbox):
    nominee = UserFactory.create()
    process = start_nomination(nominee=nominee)
    advance_to(process, "vetting")
    mailoutbox.clear()
    complete_view(process, NominationFlow.vetting, vetting_passed=False)

    assert done_task(process, NominationFlow.rejected) is not None
    process.refresh_from_db()
    assert process.rejection_sent_at is not None
    assert process.not_interested is False
    assert any(nominee.email in m.to for m in mailoutbox)
    assert Nomination.objects.filter(pk=process.pk).exists()


def test_interview_failure_sends_thank_you(mailoutbox):
    nominee = UserFactory.create()
    process = start_nomination(nominee=nominee)
    advance_to(process, "interview")
    mailoutbox.clear()
    complete_view(process, NominationFlow.interview, interview_passed=False)

    assert done_task(process, NominationFlow.rejected) is not None
    process.refresh_from_db()
    assert process.not_interested is False
    assert any(nominee.email in m.to for m in mailoutbox)


def test_future_review_allowed_after_rejection():
    nominee = UserFactory.create()
    process = start_nomination(nominee=nominee)
    advance_to(process, "vetting")
    complete_view(process, NominationFlow.vetting, vetting_passed=False)
    # not_interested was not set, so a fresh recommendation is NOT blocked.
    form = NominationForm(data={"nominee": nominee.pk, "level": ["national"], "reason": "again"})
    assert form.is_valid(), form.errors


# --- Confirmation deny: route to CentralOffice, letter upload + email
def _at_denial(**kwargs):
    process = start_nomination(**kwargs)
    advance_to(process, "confirmation")
    complete_view(process, NominationFlow.confirmation, confirmed=False)
    return process


def test_confirmation_deny_routes_to_central_office():
    process = _at_denial()
    assert active_task(process, NominationFlow.denial_central_office) is not None
    assert done_task(process, NominationFlow.denied) is None


def test_central_office_uploads_and_emails_denial_letter(auto_login_user, mailoutbox):
    co = UserFactory.create(username="co@example.com")
    Config.objects.create(key="CentralOffice", value="co@example.com", description="co")
    nominee = UserFactory.create()
    process = _at_denial(nominee=nominee)
    url = reverse("nominations:denial", kwargs={"process_pk": process.pk})
    client, _ = auto_login_user(user=co)

    client.post(
        url,
        {"action": "upload_letter", "denial_letter": SimpleUploadedFile("d.pdf", b"x"), "denial_reason": "Not a fit"},
    )
    process.refresh_from_db()
    assert process.denial_letter
    assert process.denial_reason == "Not a fit"
    assert active_task(process, NominationFlow.denial_central_office) is not None  # not done yet

    mailoutbox.clear()
    client.post(url, {"action": "email_letter"})
    process.refresh_from_db()
    assert process.denial_letter_sent_at is not None
    assert any(nominee.email in m.to for m in mailoutbox)
    # Both steps done -> flow ended (denied); record retained.
    assert done_task(process, NominationFlow.denied) is not None
    assert active_task(process, NominationFlow.denial_central_office) is None
    assert Nomination.objects.filter(pk=process.pk).exists()


def test_denial_view_gated_to_central_office(auto_login_user):
    UserFactory.create(username="co@example.com")
    Config.objects.create(key="CentralOffice", value="co@example.com", description="co")
    process = _at_denial()
    url = reverse("nominations:denial", kwargs={"process_pk": process.pk})
    client, _other = auto_login_user()
    assert client.get(url).status_code == 403
