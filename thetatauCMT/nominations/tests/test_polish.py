"""Tests for the post-VWI polish changes.

Covers: contact logging (#12), nominee progress emails (#9), the national-officer
nominations list + gating (#10), and the user-profile nomination integration
(#2/#3/#9/#14).
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.nominations.flows import NominationFlow
from thetatauCMT.nominations.forms import NominationForm
from thetatauCMT.nominations.services import complete_consent_task
from thetatauCMT.nominations.tests.factories import NominationFactory
from thetatauCMT.users.tests.factories import UserFactory

from ._flow_helpers import advance_to, complete_view, email_text, start_nomination

pytestmark = pytest.mark.django_db


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


# ---------------------------------------------------------------------------
# #12 — every contact with the nominee is captured
# ---------------------------------------------------------------------------
def test_contacts_logged_across_happy_path():
    nominee = UserFactory.create()
    process = start_nomination(nominee=nominee)  # -> consent_request contact
    process.consent_status = "interested"
    process.save()
    complete_consent_task(process)  # -> response contact
    advance_to(process, "appointment")  # -> 3 progress contacts (vetting/interview/confirmed)

    process.refresh_from_db()
    kinds = list(process.contacts.values_list("kind", flat=True))
    assert "consent_request" in kinds
    assert "response" in kinds
    assert kinds.count("progress") == 3


def test_contact_records_recipient_email():
    nominee = UserFactory.create()
    process = start_nomination(nominee=nominee)
    contact = process.contacts.get(kind="consent_request")
    assert contact.recipient == nominee.email


# ---------------------------------------------------------------------------
# #9 — the nominee is emailed progress updates as the flow advances
# ---------------------------------------------------------------------------
def test_progress_email_sent_on_vetting_pass(mailoutbox):
    nominee = UserFactory.create()
    process = start_nomination(nominee=nominee)
    process.consent_status = "interested"
    process.save()
    complete_consent_task(process)
    mailoutbox.clear()

    complete_view(process, NominationFlow.vetting, reference_check=True, vetting_passed=True)

    assert len(mailoutbox) == 1
    assert nominee.email in mailoutbox[0].to
    assert "cleared reference" in email_text(mailoutbox[0])


def test_progress_email_sent_on_confirmation(mailoutbox):
    nominee = UserFactory.create()
    process = start_nomination(nominee=nominee)
    process.consent_status = "interested"
    process.save()
    complete_consent_task(process)
    advance_to(process, "confirmation")
    mailoutbox.clear()

    complete_view(process, NominationFlow.confirmation, confirmed=True)

    assert any("confirmed" in email_text(m).lower() for m in mailoutbox)


# ---------------------------------------------------------------------------
# #10 — national-officer nominations list, gated to natoff
# ---------------------------------------------------------------------------
def test_nomination_list_redirects_non_natoff(auto_login_user):
    client, _ = auto_login_user()
    NominationFactory.create()
    response = client.get(reverse("nominations:list"))
    assert response.status_code == 302


def test_nomination_list_visible_to_natoff(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    nominee = UserFactory.create(name="Ada Lovelace")
    NominationFactory.create(nominee=nominee)
    response = client.get(reverse("nominations:list"))
    assert response.status_code == 200
    assert b"Ada Lovelace" in response.content


# ---------------------------------------------------------------------------
# #2 / #3 / #9 — profile integration
# ---------------------------------------------------------------------------
def test_profile_offers_nominate_for_other_member(auto_login_user):
    client, _ = auto_login_user()
    target = UserFactory.create()
    response = client.get(reverse("users:profile", kwargs={"username": target.username}))
    assert response.status_code == 200
    assert response.context["nominate_url"]
    assert b"Nominate" in response.content


def test_profile_greys_out_nominate_when_declined(auto_login_user):
    client, _ = auto_login_user()
    target = UserFactory.create()
    NominationFactory.create(nominee=target, not_interested=True)
    response = client.get(reverse("users:profile", kwargs={"username": target.username}))
    assert response.status_code == 200
    assert response.context["target_declined_nomination"] is True


# ---------------------------------------------------------------------------
# #14 — owner can still express interest after previously declining
# ---------------------------------------------------------------------------
def test_owner_can_express_interest_after_declining(auto_login_user):
    client, user = auto_login_user()
    NominationFactory.create(nominee=user, not_interested=True)
    response = client.get(reverse("users:profile", kwargs={"username": user.username}))
    assert response.status_code == 200
    assert response.context["can_view_nomination_status"] is True
    assert b"Express interest" in response.content


# ---------------------------------------------------------------------------
# #13 — a nominee may be recommended for multiple levels
# ---------------------------------------------------------------------------
def test_form_accepts_multiple_levels():
    nominee = UserFactory.create()
    form = NominationForm(
        data={
            "nominee": nominee.pk,
            "level": ["national", "regional"],
            "reason": "Great candidate.",
            "recommended_positions": ["grand regent"],
        }
    )
    assert form.is_valid(), form.errors
    assert "national" in form.cleaned_data["level"]
    assert "regional" in form.cleaned_data["level"]
