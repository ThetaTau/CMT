"""Tests for :mod:`thetatauCMT.contact_sync.models`."""

from datetime import timedelta

import pytest
from django.utils import timezone

from thetatauCMT.contact_sync.models import UserContactSyncToken, decrypt_token, encrypt_token
from thetatauCMT.users.tests.factories import UserFactory


def test_encrypt_token_round_trip():
    ciphertext = encrypt_token("hello-world")
    assert ciphertext != "hello-world"
    assert decrypt_token(ciphertext) == "hello-world"


def test_encrypt_empty_returns_empty():
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""


def test_decrypt_invalid_returns_empty():
    assert decrypt_token("not-a-real-token") == ""


@pytest.mark.django_db
def test_set_access_and_refresh_token_encrypt_at_rest():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_access_token("ACCESS-abc")
    token.set_refresh_token("REFRESH-xyz")
    token.save()
    token.refresh_from_db()
    assert token.get_access_token() == "ACCESS-abc"
    assert token.get_refresh_token() == "REFRESH-xyz"
    # Ciphertext must not equal the plaintext.
    assert "ACCESS-abc" not in token.access_token_encrypted
    assert "REFRESH-xyz" not in token.refresh_token_encrypted


@pytest.mark.django_db
def test_set_refresh_token_ignores_empty_value():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.set_refresh_token("original-refresh")
    token.save()
    original_ciphertext = token.refresh_token_encrypted
    # Simulate Google's "no refresh_token on refresh" behaviour: setter should
    # leave the stored value alone rather than overwriting with empty ciphertext.
    token.set_refresh_token("")
    token.save()
    token.refresh_from_db()
    assert token.refresh_token_encrypted == original_ciphertext
    assert token.get_refresh_token() == "original-refresh"


@pytest.mark.django_db
def test_is_expired_true_when_no_expiry():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    assert token.is_expired() is True


@pytest.mark.django_db
def test_is_expired_uses_leeway():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google")
    token.expires_at = timezone.now() + timedelta(seconds=30)
    # 30 seconds ahead, default 60 second leeway → considered expired.
    assert token.is_expired() is True
    token.expires_at = timezone.now() + timedelta(minutes=10)
    assert token.is_expired() is False


@pytest.mark.django_db
def test_record_sync_success_clears_error():
    user = UserFactory.create()
    token = UserContactSyncToken.objects.create(user=user, provider="google", last_error="boom")
    token.record_sync_success(count=7)
    token.refresh_from_db()
    assert token.last_sync_count == 7
    assert token.last_error == ""
    assert token.last_synced_at is not None


@pytest.mark.django_db
def test_unique_user_provider_pair():
    user = UserFactory.create()
    UserContactSyncToken.objects.create(user=user, provider="google")
    with pytest.raises(Exception):  # noqa: PT011 - IntegrityError under pg, ValidationError elsewhere
        UserContactSyncToken.objects.create(user=user, provider="google")
