"""Template-context helpers for the contact-sync modal.

The same modal (:file:`templates/contact_sync/sync_modal.html`) is embedded on
the region-officers page and on the national-officer roles page. Both pages
build the same context bag via :func:`build_sync_modal_context`.
"""

from __future__ import annotations

from django.http import HttpRequest
from django.urls import reverse

from .models import UserContactSyncToken
from .officers import NATIONAL_SCOPE, collect_contacts_for_scope, normalize_scope, scope_display_name
from .providers import PROVIDERS


def build_sync_modal_context(request: HttpRequest, scope: str) -> dict:
    """Return the template context bag consumed by ``contact_sync/sync_modal.html``.

    ``scope`` is a canonical scope string (``"region:<slug>"`` or ``"national"``);
    a bare region slug is auto-normalised via :func:`normalize_scope`.
    """
    canonical = normalize_scope(scope)
    contacts, region_display = collect_contacts_for_scope(canonical)
    if not region_display:
        region_display = scope_display_name(canonical)
    user = request.user
    tokens: dict[str, UserContactSyncToken] = {}
    if getattr(user, "is_authenticated", False):
        tokens = {t.provider: t for t in UserContactSyncToken.objects.filter(user=user)}
    providers_status: dict[str, dict] = {}
    for key, cls in PROVIDERS.items():
        token = tokens.get(key)
        auto_sync_scopes = list(getattr(token, "auto_sync_scopes", []) or []) if token else []
        providers_status[key] = {
            "label": cls.label,
            "configured": cls.is_configured(),
            "connected": bool(token),
            "account_email": token.account_email if token else "",
            "last_synced_at": (
                token.last_synced_at.strftime("%Y-%m-%d %H:%M") if token and token.last_synced_at else ""
            ),
            "last_sync_count": token.last_sync_count if token else 0,
            "last_error": token.last_error if token else "",
            "auto_sync_scopes": auto_sync_scopes,
            "auto_sync_enabled": canonical in auto_sync_scopes,
            "authorize_url": reverse(f"contact_sync:{key}_authorize"),
            "sync_url": reverse(f"contact_sync:{key}_sync"),
            "disconnect_url": reverse(f"contact_sync:{key}_disconnect"),
            "auto_sync_url": reverse(f"contact_sync:{key}_auto_sync"),
        }
    return {
        "contact_sync_available": True,
        "contact_sync_status": providers_status,
        "contact_sync_vcard_url": _vcard_url_for_scope(canonical),
        "contact_sync_status_url": reverse("contact_sync:status"),
        "contact_sync_scope": canonical,
        "contact_sync_scope_display": region_display,
        "officer_count": len(contacts),
        # Legacy vars kept for the region template's ``region_slug`` / ``region_display``.
        "region_slug": canonical.split(":", 1)[1] if canonical.startswith("region:") else canonical,
        "region_display": region_display,
    }


def _vcard_url_for_scope(scope: str) -> str:
    if scope == NATIONAL_SCOPE:
        return reverse("contact_sync:national_vcard")
    slug = scope.split(":", 1)[1] if scope.startswith("region:") else scope
    return reverse("contact_sync:region_vcard", kwargs={"region_slug": slug})
