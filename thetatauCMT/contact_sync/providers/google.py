"""Google People API sync — OAuth2 authorization code flow.

Docs:
- OAuth: https://developers.google.com/identity/protocols/oauth2/web-server
- People API createContact: https://developers.google.com/people/api/rest/v1/people/createContact
- People API updateContact: https://developers.google.com/people/api/rest/v1/people/updateContact
"""

from __future__ import annotations

import requests

from ..models import UserContactSyncToken
from ..officers import OfficerContact
from .base import ContactProvider, ProviderAuthError, SyncResult, register

PEOPLE_API_BASE = "https://people.googleapis.com/v1"
# Custom userDefined field key we write on every synced contact so we can find
# it again on the next sync and update (rather than duplicate) it.
CMT_KEY_FIELD = "cmt_officer_key"


@register
class GoogleContactsProvider(ContactProvider):
    key = "google"
    label = "Google Contacts"
    setting_client_id = "CONTACT_SYNC_GOOGLE_CLIENT_ID"
    setting_client_secret = "CONTACT_SYNC_GOOGLE_CLIENT_SECRET"
    authorize_url = "https://accounts.google.com/o/oauth2/v2/auth"
    token_url = "https://oauth2.googleapis.com/token"
    default_scopes = [
        "https://www.googleapis.com/auth/contacts",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    ]

    def authorize_params(self, *, state: str, redirect_uri: str, next_url: str) -> dict[str, str]:  # noqa: ARG002
        params = super().authorize_params(state=state, redirect_uri=redirect_uri, next_url=next_url)
        # ``access_type=offline`` requests a refresh_token; ``prompt=consent``
        # forces re-consent so we actually get one on every fresh connect.
        params["access_type"] = "offline"
        params["prompt"] = "consent"
        params["include_granted_scopes"] = "true"
        return params

    def fetch_account_email(self, access_token: str) -> str:
        response = requests.get(
            f"{PEOPLE_API_BASE}/people/me",
            params={"personFields": "emailAddresses"},
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        if response.status_code != 200:
            return ""
        try:
            data = response.json()
        except ValueError:
            return ""
        for entry in data.get("emailAddresses") or []:
            value = (entry.get("value") or "").strip()
            if value:
                return value
        return ""

    # ------------------------------------------------------------------ push
    def push_contacts(self, token: UserContactSyncToken, contacts: list[OfficerContact]) -> SyncResult:
        result = SyncResult(total=len(contacts))
        access_token = token.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        }
        existing = self._list_existing_officer_people(access_token)
        for contact in contacts:
            payload = self._contact_to_payload(contact)
            key = self._cmt_key(contact)
            resource_name = existing.get(key)
            try:
                if resource_name:
                    updated_payload = dict(payload)
                    # updateContact requires the current etag; fetch it fresh.
                    etag_response = requests.get(
                        f"{PEOPLE_API_BASE}/{resource_name}",
                        params={"personFields": "metadata"},
                        headers=headers,
                        timeout=15,
                    )
                    if etag_response.status_code == 200:
                        updated_payload["etag"] = etag_response.json().get("etag", "")
                    response = requests.patch(
                        f"{PEOPLE_API_BASE}/{resource_name}:updateContact",
                        params={
                            "updatePersonFields": "names,emailAddresses,phoneNumbers,organizations,biographies,userDefined",
                        },
                        headers=headers,
                        json=updated_payload,
                        timeout=15,
                    )
                    if response.status_code == 200:
                        result.updated += 1
                    else:
                        result.failed += 1
                        result.errors.append(f"{contact.display_name}: {response.status_code} {response.text[:200]}")
                else:
                    response = requests.post(
                        f"{PEOPLE_API_BASE}/people:createContact",
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

    def _list_existing_officer_people(self, access_token: str) -> dict[str, str]:
        """Return ``{cmt_key: resourceName}`` for previously-synced contacts."""
        out: dict[str, str] = {}
        page_token = ""
        while True:
            params = {
                "personFields": "userDefined,metadata",
                "pageSize": "500",
            }
            if page_token:
                params["pageToken"] = page_token
            response = requests.get(
                f"{PEOPLE_API_BASE}/people/me/connections",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )
            if response.status_code != 200:
                return out
            data = response.json()
            for person in data.get("connections") or []:
                for entry in person.get("userDefined") or []:
                    if entry.get("key") == CMT_KEY_FIELD and entry.get("value"):
                        out[entry["value"]] = person.get("resourceName", "")
            page_token = data.get("nextPageToken") or ""
            if not page_token:
                break
        return out

    def _contact_to_payload(self, contact: OfficerContact) -> dict:
        names = [
            {
                "givenName": contact.preferred_name or contact.first_name,
                "familyName": contact.last_name,
                "middleName": contact.middle_name,
                "honorificSuffix": contact.suffix,
                "displayName": contact.display_name,
                "unstructuredName": contact.display_name,
            }
        ]
        emails = [{"value": email, "type": "work"} for email in contact.emails]
        phones = [{"value": contact.phone, "type": "mobile"}] if contact.phone else []
        organizations = [
            {
                "name": "Theta Tau",
                "department": f"{contact.chapter_name} Chapter",
                "title": contact.role.title(),
            }
        ]
        biographies = [
            {
                "value": f"{contact.chapter_name} Chapter — {contact.role.title()}",
                "contentType": "TEXT_PLAIN",
            }
        ]
        user_defined = [
            {"key": CMT_KEY_FIELD, "value": self._cmt_key(contact)},
        ]
        return {
            "names": names,
            "emailAddresses": emails,
            "phoneNumbers": phones,
            "organizations": organizations,
            "biographies": biographies,
            "userDefined": user_defined,
        }
