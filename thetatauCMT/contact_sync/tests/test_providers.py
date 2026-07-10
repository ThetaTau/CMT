"""Tests for :mod:`thetatauCMT.contact_sync.providers`.

We exercise the OAuth exchange, token refresh, and ``push_contacts`` paths
against fake HTTP responses so we do not hit the real Google People API or
Microsoft Graph endpoints.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest
from django.test import RequestFactory, override_settings

from thetatauCMT.contact_sync.models import UserContactSyncToken
from thetatauCMT.contact_sync.officers import OfficerContact
from thetatauCMT.contact_sync.providers import (
    GoogleContactsProvider,
    MicrosoftContactsProvider,
    get_provider,
    provider_is_configured,
)
from thetatauCMT.contact_sync.providers.base import PROVIDERS, ProviderAuthError, ProviderNotConfigured
from thetatauCMT.users.tests.factories import UserFactory


class _FakeResponse:
    def __init__(self, status_code: int = 200, json_data: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.text = text or json.dumps(self._json_data)

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


def _sample_contact() -> OfficerContact:
    return OfficerContact(
        chapter_abbr="X",
        chapter_name="Chi",
        role="regent",
        role_abbr="R",
        first_name="Franklin",
        last_name="Ventura",
        email="frank@example.com",
        phone="+15551234567",
        user_pk=42,
    )


# --------------------------------------------------------------------- registry
def test_providers_registered():
    assert set(PROVIDERS) == {"google", "microsoft"}


def test_get_provider_returns_instance():
    provider = get_provider("google")
    assert isinstance(provider, GoogleContactsProvider)


def test_get_provider_unknown_key_raises():
    with pytest.raises(KeyError):
        get_provider("aol")


# --------------------------------------------------------------------- config
def test_provider_is_configured_reads_settings():
    with override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="", CONTACT_SYNC_GOOGLE_CLIENT_SECRET=""):
        assert provider_is_configured("google") is False
    with override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="secret"):
        assert provider_is_configured("google") is True


# --------------------------------------------------------------------- OAuth
def test_build_authorize_url_requires_configuration():
    provider = GoogleContactsProvider()
    with override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="", CONTACT_SYNC_GOOGLE_CLIENT_SECRET=""):
        request = RequestFactory().get("/regions/east/officers/")
        with pytest.raises(ProviderNotConfigured):
            provider.build_authorize_url(request)


def test_build_authorize_url_includes_offline_access_for_google():
    provider = GoogleContactsProvider()
    with override_settings(
        CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="secret", ALLOWED_HOSTS=["testserver"]
    ):
        request = RequestFactory().get("/regions/east/officers/")
        url, state = provider.build_authorize_url(request)
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "response_type=code" in url
    assert "state=" + state in url
    assert "client_id=id" in url


def test_microsoft_authorize_url_uses_configured_tenant():
    provider = MicrosoftContactsProvider()
    with override_settings(
        CONTACT_SYNC_MICROSOFT_CLIENT_ID="id",
        CONTACT_SYNC_MICROSOFT_CLIENT_SECRET="secret",
        CONTACT_SYNC_MICROSOFT_TENANT="contoso.onmicrosoft.com",
        ALLOWED_HOSTS=["testserver"],
    ):
        request = RequestFactory().get("/regions/east/officers/")
        url, _ = provider.build_authorize_url(request)
    assert "https://login.microsoftonline.com/contoso.onmicrosoft.com/oauth2/v2.0/authorize" in url


# --------------------------------------------------------------------- token exchange
def test_exchange_code_success_returns_json_payload():
    provider = GoogleContactsProvider()
    fake_payload = {"access_token": "AT", "refresh_token": "RT", "expires_in": 3600, "token_type": "Bearer"}
    with (
        override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s"),
        mock.patch(
            "thetatauCMT.contact_sync.providers.base.requests.post",
            return_value=_FakeResponse(200, fake_payload),
        ) as post,
    ):
        payload = provider.exchange_code(code="abc", redirect_uri="https://x/callback")
    assert payload == fake_payload
    post.assert_called_once()
    _, kwargs = post.call_args
    assert kwargs["data"]["grant_type"] == "authorization_code"


def test_exchange_code_non_200_raises():
    provider = GoogleContactsProvider()
    with (
        override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s"),
        mock.patch(
            "thetatauCMT.contact_sync.providers.base.requests.post",
            return_value=_FakeResponse(400, {"error": "bad"}, text="bad request"),
        ),
    ):
        with pytest.raises(ProviderAuthError):
            provider.exchange_code(code="abc", redirect_uri="https://x/callback")


# --------------------------------------------------------------------- refresh
@pytest.mark.django_db
def test_refresh_updates_access_token_and_expiry():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_refresh_token("OLDRT")
    token.save()
    fake_payload = {"access_token": "NEW-AT", "expires_in": 7200, "token_type": "Bearer"}
    with (
        override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s"),
        mock.patch(
            "thetatauCMT.contact_sync.providers.base.requests.post",
            return_value=_FakeResponse(200, fake_payload),
        ),
    ):
        provider = GoogleContactsProvider()
        provider.refresh(token)
    token.refresh_from_db()
    assert token.get_access_token() == "NEW-AT"
    # Refresh token preserved because Google returned none in the response.
    assert token.get_refresh_token() == "OLDRT"
    assert token.expires_at is not None


@pytest.mark.django_db
def test_refresh_requires_refresh_token():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    with (
        override_settings(CONTACT_SYNC_GOOGLE_CLIENT_ID="id", CONTACT_SYNC_GOOGLE_CLIENT_SECRET="s"),
        pytest.raises(ProviderAuthError),
    ):
        GoogleContactsProvider().refresh(token)


# --------------------------------------------------------------------- google push
@pytest.mark.django_db
def test_google_push_creates_contact_when_no_existing():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("AT")
    token.save()
    contact = _sample_contact()

    def fake_get(url, **kwargs):
        # /people/me/connections listing — return empty (no existing officer contacts).
        return _FakeResponse(200, {"connections": []})

    def fake_post(url, **kwargs):
        return _FakeResponse(201, {"resourceName": "people/c1", "etag": "e1"})

    with (
        mock.patch("thetatauCMT.contact_sync.providers.google.requests.get", side_effect=fake_get),
        mock.patch("thetatauCMT.contact_sync.providers.google.requests.post", side_effect=fake_post),
    ):
        result = GoogleContactsProvider().push_contacts(token, [contact])
    assert result.created == 1
    assert result.updated == 0
    assert result.failed == 0
    assert result.total == 1


@pytest.mark.django_db
def test_google_push_updates_existing_contact():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("AT")
    token.save()
    contact = _sample_contact()
    provider = GoogleContactsProvider()
    key = provider._cmt_key(contact)

    def fake_get(url, **kwargs):
        if "connections" in url:
            return _FakeResponse(
                200,
                {
                    "connections": [
                        {
                            "resourceName": "people/c99",
                            "userDefined": [{"key": "cmt_officer_key", "value": key}],
                        }
                    ]
                },
            )
        # Etag fetch for update.
        return _FakeResponse(200, {"etag": "the-etag"})

    def fake_patch(url, **kwargs):
        assert ":updateContact" in url
        return _FakeResponse(200, {"resourceName": "people/c99"})

    with (
        mock.patch("thetatauCMT.contact_sync.providers.google.requests.get", side_effect=fake_get),
        mock.patch("thetatauCMT.contact_sync.providers.google.requests.patch", side_effect=fake_patch),
        mock.patch("thetatauCMT.contact_sync.providers.google.requests.post") as post_mock,
    ):
        result = provider.push_contacts(token, [contact])
    assert result.updated == 1
    assert result.created == 0
    post_mock.assert_not_called()


@pytest.mark.django_db
def test_google_push_records_failure_when_all_writes_fail():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("AT")
    token.save()
    with (
        mock.patch(
            "thetatauCMT.contact_sync.providers.google.requests.get",
            return_value=_FakeResponse(200, {"connections": []}),
        ),
        mock.patch(
            "thetatauCMT.contact_sync.providers.google.requests.post",
            return_value=_FakeResponse(403, {"error": "denied"}, text="denied"),
        ),
    ):
        with pytest.raises(ProviderAuthError):
            GoogleContactsProvider().push_contacts(token, [_sample_contact()])


# --------------------------------------------------------------------- microsoft push
@pytest.mark.django_db
def test_microsoft_push_creates_contact():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="microsoft")
    token.set_access_token("AT")
    token.save()

    def fake_get(url, **kwargs):
        return _FakeResponse(200, {"value": [], "@odata.nextLink": None})

    def fake_post(url, **kwargs):
        return _FakeResponse(201, {"id": "MS-1"})

    with (
        mock.patch("thetatauCMT.contact_sync.providers.microsoft.requests.get", side_effect=fake_get),
        mock.patch("thetatauCMT.contact_sync.providers.microsoft.requests.post", side_effect=fake_post),
    ):
        result = MicrosoftContactsProvider().push_contacts(token, [_sample_contact()])
    assert result.created == 1
    assert result.updated == 0


@pytest.mark.django_db
def test_microsoft_push_updates_existing_contact():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="microsoft")
    token.set_access_token("AT")
    token.save()
    provider = MicrosoftContactsProvider()
    contact = _sample_contact()
    key = provider._cmt_key(contact)

    def fake_get(url, **kwargs):
        return _FakeResponse(
            200,
            {
                "value": [{"id": "MS-42", "personalNotes": f"CMT-KEY: {key}\nChi Chapter — Regent"}],
                "@odata.nextLink": None,
            },
        )

    def fake_patch(url, **kwargs):
        assert "/me/contacts/MS-42" in url
        return _FakeResponse(204, {})

    with (
        mock.patch("thetatauCMT.contact_sync.providers.microsoft.requests.get", side_effect=fake_get),
        mock.patch("thetatauCMT.contact_sync.providers.microsoft.requests.patch", side_effect=fake_patch),
        mock.patch("thetatauCMT.contact_sync.providers.microsoft.requests.post") as post_mock,
    ):
        result = provider.push_contacts(token, [contact])
    assert result.updated == 1
    post_mock.assert_not_called()
