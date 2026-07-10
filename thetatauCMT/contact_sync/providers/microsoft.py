"""Microsoft Graph contacts sync — OAuth2 authorization code flow.

Docs:
- Auth: https://learn.microsoft.com/graph/auth-v2-user
- List contacts: https://learn.microsoft.com/graph/api/user-list-contacts
- Create contact: https://learn.microsoft.com/graph/api/user-post-contacts
- Update contact: https://learn.microsoft.com/graph/api/contact-update
"""

from __future__ import annotations

import requests
from django.conf import settings

from ..models import UserContactSyncToken
from ..officers import OfficerContact
from .base import ContactProvider, ProviderAuthError, SyncResult, register

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
CMT_CATEGORY = "Theta Tau"


@register
class MicrosoftContactsProvider(ContactProvider):
    key = "microsoft"
    label = "Microsoft Contacts"
    setting_client_id = "CONTACT_SYNC_MICROSOFT_CLIENT_ID"
    setting_client_secret = "CONTACT_SYNC_MICROSOFT_CLIENT_SECRET"
    # ``token_url`` / ``authorize_url`` are computed dynamically because the
    # tenant is configurable (default: ``common`` = personal + work accounts).
    default_scopes = [
        "openid",
        "email",
        "offline_access",
        "Contacts.ReadWrite",
        "User.Read",
    ]

    @classmethod
    def tenant(cls) -> str:
        return (getattr(settings, "CONTACT_SYNC_MICROSOFT_TENANT", "common") or "common").strip()

    @property
    def authorize_url(self) -> str:  # type: ignore[override]
        return f"https://login.microsoftonline.com/{self.tenant()}/oauth2/v2.0/authorize"

    @property
    def token_url(self) -> str:  # type: ignore[override]
        return f"https://login.microsoftonline.com/{self.tenant()}/oauth2/v2.0/token"

    def authorize_params(self, *, state: str, redirect_uri: str, next_url: str) -> dict[str, str]:  # noqa: ARG002
        return {
            "client_id": self.client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": " ".join(self.default_scopes),
            "state": state,
            "prompt": "select_account",
        }

    def fetch_account_email(self, access_token: str) -> str:
        response = requests.get(
            f"{GRAPH_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if response.status_code != 200:
            return ""
        try:
            data = response.json()
        except ValueError:
            return ""
        return (data.get("mail") or data.get("userPrincipalName") or "").strip()

    # ------------------------------------------------------------------ push
    def push_contacts(self, token: UserContactSyncToken, contacts: list[OfficerContact]) -> SyncResult:
        result = SyncResult(total=len(contacts))
        access_token = token.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        existing = self._list_existing_officer_contacts(access_token)
        for contact in contacts:
            payload = self._contact_to_payload(contact)
            key = self._cmt_key(contact)
            existing_id = existing.get(key)
            try:
                if existing_id:
                    response = requests.patch(
                        f"{GRAPH_BASE}/me/contacts/{existing_id}",
                        headers=headers,
                        json=payload,
                        timeout=15,
                    )
                    if response.status_code in (200, 204):
                        result.updated += 1
                    else:
                        result.failed += 1
                        result.errors.append(f"{contact.display_name}: {response.status_code} {response.text[:200]}")
                else:
                    response = requests.post(
                        f"{GRAPH_BASE}/me/contacts",
                        headers=headers,
                        json=payload,
                        timeout=15,
                    )
                    if response.status_code in (200, 201):
                        result.created += 1
                    else:
                        result.failed += 1
                        result.errors.append(f"{contact.display_name}: {response.status_code} {response.text[:200]}")
            except requests.RequestException as exc:  # noqa: BLE001
                result.failed += 1
                result.errors.append(f"{contact.display_name}: {exc}")
        if result.failed and not (result.created or result.updated):
            error_msg = "; ".join(result.errors[:3])
            raise ProviderAuthError(error_msg)
        return result

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _cmt_key(contact: OfficerContact) -> str:
        return f"tt-{contact.chapter_abbr}-{contact.role_abbr}-{contact.user_pk or 'x'}".lower()

    def _list_existing_officer_contacts(self, access_token: str) -> dict[str, str]:
        """Return ``{cmt_key: contact_id}`` for previously-synced contacts.

        Uses the ``$filter`` on ``categories/any(c: c eq 'Theta Tau')`` to keep
        the response small, then reads our sentinel out of ``personalNotes``.
        """
        out: dict[str, str] = {}
        # Personal-Notes prefix we write on every synced contact.
        marker_prefix = "CMT-KEY: "
        url = (
            f"{GRAPH_BASE}/me/contacts"
            "?$select=id,personalNotes,categories"
            "&$top=100"
            f"&$filter=categories/any(c:c eq '{CMT_CATEGORY}')"
        )
        while url:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )
            if response.status_code != 200:
                return out
            data = response.json()
            for entry in data.get("value") or []:
                notes = entry.get("personalNotes") or ""
                for line in notes.splitlines():
                    line = line.strip()
                    if line.startswith(marker_prefix):
                        key = line[len(marker_prefix) :].strip()
                        if key and entry.get("id"):
                            out[key] = entry["id"]
                        break
            url = data.get("@odata.nextLink") or ""
        return out

    def _contact_to_payload(self, contact: OfficerContact) -> dict:
        given = contact.preferred_name or contact.first_name
        payload: dict = {
            "givenName": given,
            "surname": contact.last_name,
            "middleName": contact.middle_name,
            "displayName": contact.display_name,
            "nickName": contact.display_name,
            "companyName": "Theta Tau",
            "department": f"{contact.chapter_name} Chapter",
            "jobTitle": contact.role.title(),
            "categories": [CMT_CATEGORY, f"{contact.chapter_name} Chapter"],
            "personalNotes": (
                f"CMT-KEY: {self._cmt_key(contact)}\n" f"{contact.chapter_name} Chapter — {contact.role.title()}"
            ),
        }
        email_addresses = []
        for email in contact.emails:
            email_addresses.append({"address": email, "name": contact.display_name})
        if email_addresses:
            payload["emailAddresses"] = email_addresses
        if contact.phone:
            payload["mobilePhone"] = contact.phone
        return payload
