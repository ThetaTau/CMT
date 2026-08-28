"""Contact-sync HTTP views.

Endpoints (all under ``/contact-sync/``):

- ``GET  region/<slug>/vcard/``   — download officer vCard for a region.
- ``GET  national/vcard/``        — download vCard for the national officers.
- ``GET  status/``                — JSON status of connected providers.
- ``GET  <provider>/authorize/``  — start the OAuth flow.
- ``GET  <provider>/callback/``   — OAuth callback landing page.
- ``POST <provider>/sync/``       — push contacts for a scope.
- ``POST <provider>/disconnect/`` — delete stored OAuth tokens.
- ``POST <provider>/auto-sync/``  — toggle whether a scope auto-syncs weekly.

All views are gated to National Officers (or superusers). The vCard-download
paths always work; OAuth-based sync paths gracefully return errors when the
provider is not configured.
"""

from __future__ import annotations

import json

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .models import PROVIDER_CHOICES, UserContactSyncToken
from .officers import NATIONAL_SCOPE, SYNCED_OFFICER_ROLES, collect_contacts_for_scope, normalize_scope
from .providers import PROVIDERS, get_provider, provider_is_configured
from .providers.base import ProviderAuthError, ProviderNotConfigured, _apply_token_payload
from .vcard import VCARD_MIME_TYPE, build_vcard_collection


# --------------------------------------------------------------------- helpers
def _is_natoff(request: HttpRequest) -> bool:
    user = request.user
    if not user.is_authenticated:
        return False
    if user.is_admin:
        return True
    return getattr(user, "is_national_officer_group", False)


def _forbid(request: HttpRequest) -> HttpResponseRedirect:
    messages.error(request, "Only National Officers can sync officer contacts.")
    return redirect("home")


def _parse_roles(param: str | None) -> list[str] | None:
    if not param:
        return None
    roles = [r.strip().lower() for r in param.split(",") if r.strip()]
    roles = [r for r in roles if r in SYNCED_OFFICER_ROLES]
    return roles or None


def _safe_next(request: HttpRequest, fallback: str) -> str:
    next_url = request.GET.get("next") or request.POST.get("next") or ""
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback


def _scope_from_request(request: HttpRequest) -> str:
    """Return a canonical scope from the request.

    Accepts either ``scope=<canonical>`` or the legacy ``region=<slug>`` param.
    """
    scope = request.POST.get("scope") or request.GET.get("scope") or ""
    if not scope:
        region = request.POST.get("region") or request.GET.get("region") or ""
        scope = region
    return normalize_scope(scope)


def _wants_json(request: HttpRequest) -> bool:
    accepts = request.headers.get("Accept", "")
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    if "application/json" in accepts:
        return True
    if request.content_type == "application/json":
        return True
    if request.POST.get("format") == "json":
        return True
    if request.GET.get("format") == "json":
        return True
    try:
        json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        return False
    return False


# --------------------------------------------------------------------- vCard
@require_GET
def download_region_vcard(request: HttpRequest, region_slug: str) -> HttpResponse:
    if not _is_natoff(request):
        return _forbid(request)
    # Always a region scope, even when region_slug == "national" (the
    # all-chapters synthetic slug) -- normalize_scope() would otherwise
    # collapse a bare "national" into the unrelated national-council scope,
    # which has its own dedicated download_national_vcard view/URL.
    scope = f"region:{region_slug}"
    return _vcard_response(
        request,
        scope,
        filename_hint=region_slug,
        redirect_on_empty="regions:officers",
        redirect_kwargs={"slug": region_slug},
    )


@require_GET
def download_national_vcard(request: HttpRequest) -> HttpResponse:
    if not _is_natoff(request):
        return _forbid(request)
    return _vcard_response(request, NATIONAL_SCOPE, filename_hint="national", redirect_on_empty="forms:natoff")


def _vcard_response(
    request: HttpRequest,
    scope: str,
    *,
    filename_hint: str,
    redirect_on_empty: str,
    redirect_kwargs: dict | None = None,
) -> HttpResponse:
    roles = _parse_roles(request.GET.get("roles"))
    contacts, scope_display = collect_contacts_for_scope(scope, roles=roles)
    if not contacts:
        messages.warning(request, "No matching officers to export.")
        return redirect(redirect_on_empty, **(redirect_kwargs or {}))
    body = build_vcard_collection(contacts)
    filename = f"ThetaTau_{filename_hint}_officers_{timezone.now().strftime('%Y%m%d')}.vcf"
    response = HttpResponse(body, content_type=VCARD_MIME_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-CMT-Officer-Count"] = str(len(contacts))
    response["X-CMT-Scope"] = scope
    response["X-CMT-Scope-Display"] = scope_display
    return response


# --------------------------------------------------------------------- status
@require_GET
def sync_status(request: HttpRequest) -> JsonResponse:
    if not _is_natoff(request):
        return JsonResponse({"error": "forbidden"}, status=403)
    out: dict[str, dict] = {}
    tokens = {t.provider: t for t in UserContactSyncToken.objects.filter(user=request.user)}
    for key, cls in PROVIDERS.items():
        token = tokens.get(key)
        auto_scopes = list(getattr(token, "auto_sync_scopes", []) or []) if token else []
        out[key] = {
            "label": cls.label,
            "configured": cls.is_configured(),
            "connected": bool(token),
            "account_email": token.account_email if token else "",
            "last_synced_at": token.last_synced_at.isoformat() if token and token.last_synced_at else "",
            "last_sync_count": token.last_sync_count if token else 0,
            "last_error": token.last_error if token else "",
            "auto_sync_scopes": auto_scopes,
            "authorize_url": reverse(f"contact_sync:{key}_authorize"),
            "sync_url": reverse(f"contact_sync:{key}_sync"),
            "disconnect_url": reverse(f"contact_sync:{key}_disconnect"),
            "auto_sync_url": reverse(f"contact_sync:{key}_auto_sync"),
        }
    return JsonResponse({"providers": out, "roles": list(SYNCED_OFFICER_ROLES)})


# --------------------------------------------------------------------- OAuth
@require_GET
def oauth_authorize(request: HttpRequest, provider_key: str) -> HttpResponse:
    if not _is_natoff(request):
        return _forbid(request)
    if provider_key not in PROVIDERS:
        messages.error(request, "Unknown contact provider.")
        return redirect("home")
    if not provider_is_configured(provider_key):
        messages.error(
            request,
            f"{PROVIDERS[provider_key].label} is not configured on this server. "
            "Ask an administrator to set the client ID and secret.",
        )
        return redirect(_safe_next(request, "home"))
    provider = get_provider(provider_key)
    try:
        url, state = provider.build_authorize_url(
            request,
            next_url=_safe_next(request, ""),
        )
    except ProviderNotConfigured as exc:
        messages.error(request, str(exc))
        return redirect("home")
    request.session[_state_key(provider_key)] = state
    request.session[_next_key(provider_key)] = _safe_next(request, "")
    return HttpResponseRedirect(url)


@require_GET
def oauth_callback(request: HttpRequest, provider_key: str) -> HttpResponse:
    if not _is_natoff(request):
        return _forbid(request)
    if provider_key not in PROVIDERS:
        messages.error(request, "Unknown contact provider.")
        return redirect("home")
    error = request.GET.get("error")
    if error:
        description = request.GET.get("error_description") or error
        messages.error(request, f"{PROVIDERS[provider_key].label} sign-in failed: {description}")
        return redirect(_safe_next(request, "home"))
    state = request.GET.get("state") or ""
    saved_state = request.session.pop(_state_key(provider_key), "")
    next_url = request.session.pop(_next_key(provider_key), "") or "home"
    if not state or state != saved_state:
        messages.error(request, "Contact-sync OAuth state mismatch. Please try again.")
        return redirect(next_url or "home")
    code = request.GET.get("code") or ""
    if not code:
        messages.error(request, "Missing authorization code from provider.")
        return redirect(next_url or "home")
    provider = get_provider(provider_key)
    try:
        payload = provider.exchange_code(code=code, redirect_uri=provider.redirect_uri(request))
    except (ProviderAuthError, ProviderNotConfigured) as exc:
        messages.error(request, f"{provider.label} sign-in failed: {exc}")
        return redirect(next_url or "home")
    token, _ = UserContactSyncToken.objects.get_or_create(
        user=request.user,
        provider=provider_key,
    )
    _apply_token_payload(token, payload)
    account_email = provider.fetch_account_email(token.get_access_token()) if token.get_access_token() else ""
    if account_email:
        token.account_email = account_email
    token.last_error = ""
    token.save()
    messages.success(
        request,
        f"Connected {provider.label}" + (f" as {account_email}." if account_email else "."),
    )
    return render(
        request,
        "contact_sync/oauth_callback.html",
        {
            "provider": provider,
            "next_url": next_url or reverse("home"),
            "account_email": account_email,
        },
    )


@require_POST
def oauth_disconnect(request: HttpRequest, provider_key: str) -> HttpResponse:
    if not _is_natoff(request):
        return _forbid(request)
    if provider_key not in PROVIDERS:
        return JsonResponse({"error": "unknown provider"}, status=400)
    UserContactSyncToken.objects.filter(user=request.user, provider=provider_key).delete()
    if _wants_json(request):
        return JsonResponse({"ok": True, "provider": provider_key, "connected": False})
    messages.success(request, f"Disconnected your {PROVIDERS[provider_key].label} account.")
    return redirect(_safe_next(request, "home"))


# --------------------------------------------------------------------- sync
@require_POST
def provider_sync(request: HttpRequest, provider_key: str) -> HttpResponse:
    if not _is_natoff(request):
        return JsonResponse({"error": "forbidden"}, status=403)
    if provider_key not in PROVIDERS:
        return JsonResponse({"error": "unknown provider"}, status=400)
    if not provider_is_configured(provider_key):
        return JsonResponse(
            {"error": f"{PROVIDERS[provider_key].label} is not configured on this server."},
            status=400,
        )
    scope = _scope_from_request(request)
    if not scope:
        return JsonResponse({"error": "scope is required"}, status=400)
    try:
        token = UserContactSyncToken.objects.get(user=request.user, provider=provider_key)
    except UserContactSyncToken.DoesNotExist:
        return JsonResponse(
            {"error": f"Not connected to {PROVIDERS[provider_key].label}. Connect first.", "connected": False},
            status=400,
        )
    roles = _parse_roles(request.POST.get("roles"))
    contacts, scope_display = collect_contacts_for_scope(scope, roles=roles)
    if not contacts:
        return JsonResponse(
            {"ok": True, "count": 0, "scope": scope, "scope_display": scope_display, "message": "No matching officers."}
        )
    provider = get_provider(provider_key)
    try:
        provider.ensure_valid(token)
    except (ProviderAuthError, ProviderNotConfigured) as exc:
        token.record_sync_error(str(exc))
        return JsonResponse(
            {"error": f"Reconnect required: {exc}", "connected": False},
            status=400,
        )
    try:
        result = provider.push_contacts(token, contacts)
    except (ProviderAuthError, ProviderNotConfigured) as exc:
        token.record_sync_error(str(exc))
        return JsonResponse({"error": str(exc), "connected": True}, status=502)
    token.record_sync_success(result.created + result.updated)
    return JsonResponse(
        {
            "ok": True,
            "scope": scope,
            "scope_display": scope_display,
            "created": result.created,
            "updated": result.updated,
            "failed": result.failed,
            "total": result.total,
            "errors": result.errors[:10],
            "last_synced_at": token.last_synced_at.isoformat() if token.last_synced_at else "",
        }
    )


# --------------------------------------------------------------------- auto-sync toggle
@require_POST
def provider_auto_sync(request: HttpRequest, provider_key: str) -> HttpResponse:
    """Add or remove a scope from the token's weekly auto-sync list."""
    if not _is_natoff(request):
        return JsonResponse({"error": "forbidden"}, status=403)
    if provider_key not in PROVIDERS:
        return JsonResponse({"error": "unknown provider"}, status=400)
    scope = _scope_from_request(request)
    if not scope:
        return JsonResponse({"error": "scope is required"}, status=400)
    enabled_raw = (request.POST.get("enabled") or "").strip().lower()
    enabled = enabled_raw in {"1", "true", "yes", "on"}
    try:
        token = UserContactSyncToken.objects.get(user=request.user, provider=provider_key)
    except UserContactSyncToken.DoesNotExist:
        return JsonResponse(
            {"error": f"Not connected to {PROVIDERS[provider_key].label}. Connect first.", "connected": False},
            status=400,
        )
    new_state = token.set_scope_auto_sync(scope, enabled)
    return JsonResponse(
        {
            "ok": True,
            "provider": provider_key,
            "scope": scope,
            "enabled": new_state,
            "auto_sync_scopes": list(token.auto_sync_scopes or []),
        }
    )


# --------------------------------------------------------------------- session-key helpers
def _state_key(provider_key: str) -> str:
    return f"contact_sync:{provider_key}:oauth_state"


def _next_key(provider_key: str) -> str:
    return f"contact_sync:{provider_key}:next"


# Expose the provider choices used by templates.
__all__ = [
    "PROVIDER_CHOICES",
    "download_national_vcard",
    "download_region_vcard",
    "oauth_authorize",
    "oauth_callback",
    "oauth_disconnect",
    "provider_auto_sync",
    "provider_sync",
    "sync_status",
]
