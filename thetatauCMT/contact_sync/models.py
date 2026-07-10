"""Persistence for per-user OAuth tokens used by contact-sync providers.

Refresh tokens are stored encrypted at rest with :class:`cryptography.fernet.Fernet`.
The key is derived deterministically from ``settings.SECRET_KEY`` so we do not
have to introduce a new secret in the operator's environment — but note the
consequence: rotating ``SECRET_KEY`` invalidates all stored tokens and every
national officer must reconnect their provider account.
"""

from __future__ import annotations

import base64
import hashlib
from datetime import timedelta

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel

PROVIDER_CHOICES = [
    ("google", "Google Contacts"),
    ("microsoft", "Microsoft Contacts"),
]


def _fernet() -> Fernet:
    # Fernet keys must be a URL-safe base64-encoded 32-byte value. Derive it
    # via SHA-256 so the key length is always right regardless of SECRET_KEY.
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_token(value: str) -> str:
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_token(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


class UserContactSyncToken(TimeStampedModel):
    """OAuth token bundle for one (user, provider) pair.

    ``access_token`` / ``refresh_token`` are stored ciphertext-only; use the
    ``get_access_token`` / ``get_refresh_token`` helpers instead of touching the
    fields directly.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="contact_sync_tokens",
    )
    provider = models.CharField(max_length=32, choices=PROVIDER_CHOICES)
    access_token_encrypted = models.TextField(blank=True, default="")
    refresh_token_encrypted = models.TextField(blank=True, default="")
    token_type = models.CharField(max_length=32, blank=True, default="Bearer")
    scope = models.TextField(blank=True, default="")
    account_email = models.EmailField(blank=True, default="")
    expires_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    # Free-form scope strings that should be pushed on each scheduled run.
    # Values follow :mod:`contact_sync.officers`: ``"national"``,
    # ``"region:<slug>"``. Empty list == no auto-sync (manual only).
    auto_sync_scopes = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Scopes to push on each scheduled run — 'national' or 'region:<slug>'.",
    )

    class Meta:
        unique_together = (("user", "provider"),)
        ordering = ("provider", "user_id")

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.get_provider_display()} — {self.account_email or self.user}"

    # ------------------------------------------------------------------ helpers
    def get_access_token(self) -> str:
        return decrypt_token(self.access_token_encrypted)

    def get_refresh_token(self) -> str:
        return decrypt_token(self.refresh_token_encrypted)

    def set_access_token(self, value: str) -> None:
        self.access_token_encrypted = encrypt_token(value or "")

    def set_refresh_token(self, value: str) -> None:
        # Google occasionally returns no new refresh_token on refresh — do not
        # clobber a stored refresh_token with an empty string in that case.
        if not value:
            return
        self.refresh_token_encrypted = encrypt_token(value)

    def is_expired(self, *, leeway_seconds: int = 60) -> bool:
        if not self.expires_at:
            return True
        return timezone.now() >= self.expires_at - timedelta(seconds=leeway_seconds)

    def record_sync_success(self, count: int) -> None:
        self.last_synced_at = timezone.now()
        self.last_sync_count = count
        self.last_error = ""
        self.save(update_fields=["last_synced_at", "last_sync_count", "last_error", "modified"])

    def record_sync_error(self, message: str) -> None:
        self.last_error = (message or "")[:2000]
        self.save(update_fields=["last_error", "modified"])

    # -------------------------------------------------------- schedule helpers
    def set_scope_auto_sync(self, scope: str, enabled: bool) -> bool:
        """Toggle whether ``scope`` is included in the weekly auto-sync.

        Returns the new value of ``scope in self.auto_sync_scopes``. Saves
        only when the state actually changes so we don't spam the audit trail.
        """
        scope = (scope or "").strip()
        if not scope:
            return False
        scopes = list(self.auto_sync_scopes or [])
        in_list = scope in scopes
        if enabled and not in_list:
            scopes.append(scope)
        elif not enabled and in_list:
            scopes = [s for s in scopes if s != scope]
        else:
            return in_list
        self.auto_sync_scopes = scopes
        self.save(update_fields=["auto_sync_scopes", "modified"])
        return enabled
