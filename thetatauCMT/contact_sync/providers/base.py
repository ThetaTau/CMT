"""Provider base class + registry for contact-sync integrations."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta
from typing import ClassVar

import requests
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from ..models import UserContactSyncToken


@dataclass
class SyncResult:
    """Outcome of a single provider sync call."""

    created: int = 0
    updated: int = 0
    failed: int = 0
    total: int = 0
    errors: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


class ProviderNotConfigured(RuntimeError):
    """Raised when a provider's client ID / secret is missing."""


class ProviderAuthError(RuntimeError):
    """Raised when OAuth exchange or token refresh fails."""


class ContactProvider:
    """Abstract base for OAuth2 contact-sync providers.

    Subclasses set ``key``, ``label``, ``authorize_url``, ``token_url``, and
    ``default_scopes``, plus the client-credentials attribute names on
    :data:`django.conf.settings`.
    """

    key: ClassVar[str] = ""
    label: ClassVar[str] = ""
    setting_client_id: ClassVar[str] = ""
    setting_client_secret: ClassVar[str] = ""
    authorize_url: ClassVar[str] = ""
    token_url: ClassVar[str] = ""
    default_scopes: ClassVar[list[str]] = []

    def __init__(self) -> None:
        if not self.key:
            error_msg = f"{type(self).__name__} must set a non-empty ``key``"
            raise TypeError(error_msg)

    # ------------------------------------------------------------------ config
    @classmethod
    def client_id(cls) -> str:
        return (getattr(settings, cls.setting_client_id, "") or "").strip()

    @classmethod
    def client_secret(cls) -> str:
        return (getattr(settings, cls.setting_client_secret, "") or "").strip()

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.client_id() and cls.client_secret())

    def redirect_uri(self, request) -> str:
        path = reverse(f"contact_sync:{self.key}_callback")
        return request.build_absolute_uri(path)

    # ------------------------------------------------------------------ oauth
    def build_authorize_url(self, request, *, next_url: str = "") -> tuple[str, str]:
        """Return ``(authorize_url, state)`` for the OAuth consent redirect."""
        if not self.is_configured():
            error_msg = f"Provider {self.key!r} is not configured."
            raise ProviderNotConfigured(error_msg)
        state = secrets.token_urlsafe(32)
        params = self.authorize_params(state=state, redirect_uri=self.redirect_uri(request), next_url=next_url)
        url = f"{self.authorize_url}?{_urlencode(params)}"
        return url, state

    def authorize_params(self, *, state: str, redirect_uri: str, next_url: str) -> dict[str, str]:  # noqa: ARG002
        return {
            "client_id": self.client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.default_scopes),
            "state": state,
        }

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict:
        """Exchange an OAuth code for tokens. Returns the raw provider JSON."""
        if not self.is_configured():
            error_msg = f"Provider {self.key!r} is not configured."
            raise ProviderNotConfigured(error_msg)
        payload = {
            "code": code,
            "client_id": self.client_id(),
            "client_secret": self.client_secret(),
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        return self._post_token(payload)

    def refresh(self, token: UserContactSyncToken) -> UserContactSyncToken:
        """Refresh the given token in-place (if a refresh_token is stored)."""
        if not self.is_configured():
            error_msg = f"Provider {self.key!r} is not configured."
            raise ProviderNotConfigured(error_msg)
        refresh_token = token.get_refresh_token()
        if not refresh_token:
            error_msg = f"No refresh token stored for {self.key}."
            raise ProviderAuthError(error_msg)
        payload = {
            "refresh_token": refresh_token,
            "client_id": self.client_id(),
            "client_secret": self.client_secret(),
            "grant_type": "refresh_token",
        }
        data = self._post_token(payload)
        _apply_token_payload(token, data)
        token.save()
        return token

    def _post_token(self, payload: dict) -> dict:
        response = requests.post(self.token_url, data=payload, timeout=15)
        if response.status_code != 200:
            error_msg = f"{self.label} token endpoint returned {response.status_code}: {response.text[:400]}"
            raise ProviderAuthError(error_msg)
        try:
            return response.json()
        except ValueError as exc:  # noqa: BLE001
            error_msg = f"{self.label} token endpoint returned non-JSON: {response.text[:200]}"
            raise ProviderAuthError(error_msg) from exc

    def ensure_valid(self, token: UserContactSyncToken) -> UserContactSyncToken:
        if token.is_expired():
            return self.refresh(token)
        return token

    # ------------------------------------------------------------------ profile
    def fetch_account_email(self, access_token: str) -> str:  # noqa: ARG002
        """Return the email of the authenticated user (best-effort)."""
        return ""

    # ------------------------------------------------------------------ push
    def push_contacts(self, token: UserContactSyncToken, contacts: list) -> SyncResult:
        raise NotImplementedError


# --------------------------------------------------------------------- helpers
def _urlencode(params: dict[str, str]) -> str:
    from urllib.parse import urlencode

    return urlencode(params)


def _apply_token_payload(token: UserContactSyncToken, payload: dict) -> None:
    if "access_token" in payload:
        token.set_access_token(payload["access_token"])
    if "refresh_token" in payload:
        token.set_refresh_token(payload["refresh_token"])
    token.token_type = payload.get("token_type", token.token_type or "Bearer")
    scope = payload.get("scope")
    if scope:
        token.scope = scope
    if "expires_in" in payload:
        try:
            expires_in = int(payload["expires_in"])
        except (TypeError, ValueError):
            expires_in = 0
        if expires_in > 0:
            token.expires_at = timezone.now() + timedelta(seconds=expires_in)


# --------------------------------------------------------------------- registry
PROVIDERS: dict[str, type[ContactProvider]] = {}


def register(cls: type[ContactProvider]) -> type[ContactProvider]:
    PROVIDERS[cls.key] = cls
    return cls


def get_provider(key: str) -> ContactProvider:
    provider_cls = PROVIDERS.get(key)
    if provider_cls is None:
        error_msg = f"Unknown contact-sync provider: {key!r}"
        raise KeyError(error_msg)
    return provider_cls()


def provider_is_configured(key: str) -> bool:
    provider_cls = PROVIDERS.get(key)
    return bool(provider_cls and provider_cls.is_configured())
