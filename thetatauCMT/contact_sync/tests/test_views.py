"""Tests for the contact-sync HTTP views."""

from __future__ import annotations

import json
from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse

from thetatauCMT.contact_sync.models import UserContactSyncToken
from thetatauCMT.users.tests.factories import UserFactory, UserRoleChangeFactory


def _make_natoff(user, client):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


def _seed_regent(chapter, **extra) -> None:
    user = UserFactory.create(
        chapter=chapter,
        first_name=extra.get("first_name", "Regent"),
        last_name=extra.get("last_name", chapter.name.title()),
        email=extra.get("email", f"{chapter.slug}-regent@example.com"),
        phone_number=extra.get("phone_number", "+15551234567"),
    )
    UserRoleChangeFactory.create(user=user, role="regent", current=True)
    user.refresh_from_db()
    current = set(user.current_roles or [])
    current.add("regent")
    user.current_roles = list(current)
    user.save(update_fields=["current_roles"])


# --------------------------------------------------------------------- vCard
@pytest.mark.django_db
def test_vcard_download_returns_vcf(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    chapter = user.current_chapter
    _seed_regent(chapter, first_name="Franklin", last_name="Ventura", email="fv@example.com")
    url = reverse("contact_sync:region_vcard", kwargs={"region_slug": chapter.region.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/vcard")
    body = response.content.decode("utf-8")
    assert "BEGIN:VCARD" in body
    assert "END:VCARD" in body
    # Officer count header lets the UI show a preview without re-fetching.
    assert int(response["X-CMT-Officer-Count"]) >= 1


@pytest.mark.django_db
def test_vcard_download_forbidden_for_non_natoff(auto_login_user):
    client, user = auto_login_user()
    chapter = user.current_chapter
    url = reverse("contact_sync:region_vcard", kwargs={"region_slug": chapter.region.slug})
    response = client.get(url)
    assert response.status_code == 302
    assert response["Location"].startswith("/") or "home" in response["Location"]


@pytest.mark.django_db
def test_vcard_download_unauthenticated_redirects_to_login(client):
    response = client.get(reverse("contact_sync:region_vcard", kwargs={"region_slug": "east"}))
    assert response.status_code == 302


# --------------------------------------------------------------------- status
@pytest.mark.django_db
def test_status_endpoint_returns_provider_map(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    response = client.get(reverse("contact_sync:status"))
    assert response.status_code == 200
    data = response.json()
    assert set(data["providers"]) == {"google", "microsoft"}
    for key in ("google", "microsoft"):
        entry = data["providers"][key]
        assert "authorize_url" in entry
        assert "sync_url" in entry
        assert "connected" in entry
    assert "regent" in data["roles"]


@pytest.mark.django_db
def test_status_endpoint_forbidden_for_non_natoff(auto_login_user):
    client, user = auto_login_user()
    response = client.get(reverse("contact_sync:status"))
    assert response.status_code == 403


# --------------------------------------------------------------------- OAuth
@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="")
def test_oauth_authorize_returns_error_message_when_not_configured(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    response = client.get(reverse("contact_sync:google_authorize"))
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="secret")
def test_oauth_authorize_redirects_to_provider_and_stores_state(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    response = client.get(reverse("contact_sync:google_authorize"))
    assert response.status_code == 302
    assert "accounts.google.com" in response["Location"]
    assert "state=" in response["Location"]
    # State also lives in the session so the callback can validate it.
    session = client.session
    saved_state = session.get("contact_sync:google:oauth_state")
    assert saved_state
    assert saved_state in response["Location"]


@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="secret")
def test_oauth_callback_state_mismatch_rejected(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    session = client.session
    session["contact_sync:google:oauth_state"] = "correct-state"
    session.save()
    response = client.get(
        reverse("contact_sync:google_callback"),
        {"code": "the-code", "state": "wrong-state"},
    )
    # 302 back to next url (which defaults to 'home' when unset).
    assert response.status_code == 302
    # No token should have been created.
    assert UserContactSyncToken.objects.filter(user=user, provider="google").count() == 0


@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="secret")
def test_oauth_callback_stores_token_on_success(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    session = client.session
    session["contact_sync:google:oauth_state"] = "correct-state"
    session.save()

    fake_token_response = mock.Mock()
    fake_token_response.status_code = 200
    fake_token_response.json.return_value = {
        "access_token": "AT-42",
        "refresh_token": "RT-42",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/contacts",
    }
    fake_token_response.text = "{}"

    with (
        mock.patch(
            "thetatauCMT.contact_sync.providers.base.requests.post",
            return_value=fake_token_response,
        ),
        mock.patch(
            "thetatauCMT.contact_sync.providers.google.GoogleContactsProvider.fetch_account_email",
            return_value="natoff@example.com",
        ),
    ):
        response = client.get(
            reverse("contact_sync:google_callback"),
            {"code": "abcdef", "state": "correct-state"},
        )
    assert response.status_code == 200
    token = UserContactSyncToken.objects.get(user=user, provider="google")
    assert token.get_access_token() == "AT-42"
    assert token.get_refresh_token() == "RT-42"
    assert token.account_email == "natoff@example.com"


# --------------------------------------------------------------------- sync
@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s")
def test_sync_requires_connected_token(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    chapter = user.current_chapter
    response = client.post(
        reverse("contact_sync:google_sync"),
        {"region": chapter.region.slug},
    )
    assert response.status_code == 400
    data = json.loads(response.content)
    assert data.get("connected") is False


@pytest.mark.django_db
@override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s")
def test_sync_pushes_contacts_and_records_success(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    chapter = user.current_chapter
    _seed_regent(chapter)
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("AT")
    from datetime import timedelta

    from django.utils import timezone

    token.expires_at = timezone.now() + timedelta(hours=1)
    token.save()

    from thetatauCMT.contact_sync.providers.base import SyncResult

    with mock.patch(
        "thetatauCMT.contact_sync.providers.google.GoogleContactsProvider.push_contacts",
        return_value=SyncResult(created=1, updated=0, failed=0, total=1),
    ):
        response = client.post(
            reverse("contact_sync:google_sync"),
            {"region": chapter.region.slug},
        )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["created"] == 1
    token.refresh_from_db()
    assert token.last_sync_count == 1
    assert token.last_synced_at is not None


@pytest.mark.django_db
def test_sync_forbidden_for_non_natoff(auto_login_user):
    client, user = auto_login_user()
    chapter = user.current_chapter
    response = client.post(
        reverse("contact_sync:google_sync"),
        {"region": chapter.region.slug},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------- disconnect
@pytest.mark.django_db
def test_disconnect_deletes_token(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    UserContactSyncToken.objects.create(user=user, provider="google")
    response = client.post(reverse("contact_sync:google_disconnect"), {"format": "json"})
    assert response.status_code == 200
    assert UserContactSyncToken.objects.filter(user=user, provider="google").count() == 0


# --------------------------------------------------------------------- integration with region page
@pytest.mark.django_db
def test_region_officers_page_includes_sync_button_and_modal(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client)
    chapter = user.current_chapter
    _seed_regent(chapter)
    response = client.get(reverse("regions:officers", kwargs={"slug": chapter.region.slug}))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Sync to Contacts" in body
    assert 'id="contactSyncModal"' in body
    # vCard link should reference the region slug.
    assert reverse("contact_sync:region_vcard", kwargs={"region_slug": chapter.region.slug}) in body
