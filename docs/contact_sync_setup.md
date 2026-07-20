# Contact Sync setup guide

The **Sync to Contacts** button on `/regions/<slug>/officers/` lets National
Officers push chapter-officer contacts (Regent, Vice Regent, Treasurer, Scribe,
Corresponding Secretary) from every chapter in a region into their personal
address book.

Contacts are named `ChapterAbbr-Pos First Last` — e.g. `X-R Franklin Ventura`.

Three integration paths are supported:

| Provider                | Setup required                        | What happens                              |
| ----------------------- | ------------------------------------- | ----------------------------------------- |
| **Google Contacts**     | Google Cloud OAuth client (see below) | Direct sync via People API                |
| **Microsoft / Outlook** | Entra ID app registration (see below) | Direct sync via Microsoft Graph           |
| **Apple / iCloud**      | Nothing — always available            | Download `.vcf`, import into Contacts app |
| **Any other**           | Nothing — always available            | Download `.vcf`, import anywhere          |

If Google or Microsoft is not configured, that tab in the dialog explains what
is missing and points here. The vCard-download path always works, so the feature
is functional out of the box for every national officer — configuration only
adds the "one-click direct sync" ergonomics.

---

## 1. Google Contacts (Google People API)

### 1a. Create an OAuth 2.0 Web Client in Google Cloud

1. Sign in to [Google Cloud Console](https://console.cloud.google.com/) with the
   Theta Tau workspace account and pick (or create) a project.
2. Enable the **People API** for the project:
   `APIs & Services → Library → People API → Enable`.
3. Go to `APIs & Services → OAuth consent screen`:
   - **User type**: `External` (or `Internal` if you're inside the Theta Tau
     Workspace org).
   - **Scopes**: add `https://www.googleapis.com/auth/contacts` and
     `https://www.googleapis.com/auth/userinfo.email`. `openid` is implicit.
   - **Test users**: add every National Officer email that will use this before
     you publish the app (or click "Publish app" once you're comfortable).
4. Go to `APIs & Services → Credentials → Create Credentials → OAuth client ID`:
   - **Application type**: `Web application`
   - **Authorized redirect URIs**:
     - `https://cmt.thetatau.org/contact-sync/google/callback/` (production)
     - `https://YOUR-STAGING-HOST/contact-sync/google/callback/` (staging)
     - `http://localhost:8000/contact-sync/google/callback/` (local dev)
5. Copy the **Client ID** and **Client secret** — you'll paste them into the
   Django environment in step 1b.

### 1b. Configure the Django app

Add two environment variables (see `config/settings/base.py` for the exact
names). For production this typically lives in `.env` next to the compose file:

```env
CONTACT_SYNC_GOOGLE_CLIENT_ID=1234567890-abcd.apps.googleusercontent.com
CONTACT_SYNC_GOOGLE_CLIENT_SECRET=GOCSPX-your-secret-here
```

Restart the Django service so the new settings load
(`docker-compose -f docker-compose.local.yml restart django` or the production
equivalent). No migrations are required — the tokens table is created by the
`0001_initial` migration in `thetatauCMT/contact_sync/migrations/`.

### 1c. Try it

- Sign in as a national officer and go to any `/regions/<slug>/officers/` page.
- Click **Sync to Contacts** → **Google** → **Connect**.
- Complete the Google consent screen in the popup.
- Back on the officers page, click **Sync N contacts**. On success you'll see
  the count of created / updated contacts.

Members can revoke access at any time from
[https://myaccount.google.com/permissions](https://myaccount.google.com/permissions).

---

## 2. Microsoft / Outlook Contacts (Microsoft Graph)

### 2a. Register an app in Microsoft Entra ID (Azure AD)

1. Sign in to
   [Microsoft Entra admin center](https://entra.microsoft.com/) as an
   administrator of the Theta Tau tenant (or your test tenant).
2. Go to `Identity → Applications → App registrations → New registration`.
3. Fill in:
   - **Name**: `Theta Tau CMT — Contact Sync`
   - **Supported account types**: choose based on your audience:
     - `Accounts in any organizational directory and personal Microsoft accounts`
       for the widest reach (matches the default `common` tenant).
     - `Accounts in this organizational directory only` if you only want internal
       Theta Tau accounts (then set `CONTACT_SYNC_MICROSOFT_TENANT` to the tenant
       GUID or verified domain).
   - **Redirect URI**: `Web` +
     `https://cmt.thetatau.org/contact-sync/microsoft/callback/`. Add the
     staging / localhost equivalents afterwards under
     `Manage → Authentication → Redirect URIs`.
4. Under `Manage → API permissions` add these **delegated** permissions from
   **Microsoft Graph**:
   - `openid`
   - `email`
   - `offline_access`
   - `Contacts.ReadWrite`
   - `User.Read`
   Click `Grant admin consent for <tenant>` afterwards.
5. Under `Manage → Certificates & secrets → New client secret` create a secret
   with 24-month expiry, copy the **Value** (not the Secret ID).
6. Copy the **Application (client) ID** from the app's Overview page.

### 2b. Configure the Django app

```env
CONTACT_SYNC_MICROSOFT_CLIENT_ID=00000000-1111-2222-3333-444444444444
CONTACT_SYNC_MICROSOFT_CLIENT_SECRET=your-client-secret-value
# Optional — defaults to "common" (personal + any work/school account).
# Set to a tenant GUID or verified domain to restrict.
CONTACT_SYNC_MICROSOFT_TENANT=common
```

Restart the Django service.

### 2c. Try it

Same as Google: **Sync to Contacts** → **Microsoft** → **Connect**. Users can
revoke access from
[https://myaccount.microsoft.com/](https://myaccount.microsoft.com/) →
`Privacy → App permissions & consent`.

---

## 3. Apple / iCloud (vCard download)

Apple does not offer a public OAuth-based API for iCloud Contacts, so we
**cannot** push contacts directly to iCloud. Instead:

1. Click **Sync to Contacts** → **Apple** → **Download vCard**.
2. Open the `.vcf` file:
   - **macOS**: double-click → Contacts.app prompts to add all cards.
   - **iOS**: open the attachment → *Share* → *Contacts* → *Add All Contacts*.
3. iCloud sync propagates the new cards to every device signed into the same
   Apple ID.

The **Other / vCard** tab does the same thing under a more generic label — the
same `.vcf` file works with Fastmail, Nextcloud, Thunderbird, any CardDAV
client, Google Contacts (Import), Outlook (Import), etc.

---

## About "Microsoft Universal Directory Sync"

If someone has suggested using **Microsoft Entra ID directory sync / SCIM
provisioning** for this, note that those tools solve a *different* problem: they
provision **user accounts** into an Entra directory so that IT can centrally
manage sign-ins, groups, and licenses. They do not write into any individual
officer's *personal* Outlook Contacts list.

For the "put chapter officers in my phone" use case, the Microsoft Graph
integration described above is the right primitive: it uses each officer's own
Microsoft account and writes into their personal Contacts folder, which then
syncs to Outlook, Outlook mobile, and (via the Outlook connector) to iPhone /
Android address books.

---

## Rotating secrets

Refresh tokens are stored ciphertext-only in `contact_sync_usercontactsynctoken`,
encrypted with a key derived from `SECRET_KEY`. **Rotating `SECRET_KEY`
invalidates every stored token** — every national officer will need to click
**Connect** again on the next sync. Plan rotations accordingly.

To force everyone to reconnect (e.g. after revoking the OAuth client), truncate
the table:

```sh
podman exec thetataucmt_local_django python manage.py shell -c \
  "from thetatauCMT.contact_sync.models import UserContactSyncToken; UserContactSyncToken.objects.all().delete()"
```

---

## Removing the feature

If you want to hide the button entirely (e.g. during initial rollout):

- Set both `CONTACT_SYNC_GOOGLE_CLIENT_ID` and `CONTACT_SYNC_MICROSOFT_CLIENT_ID`
  to empty strings — only the vCard-download path remains available.
- Or comment out the `path("contact-sync/", ...)` include in `config/urls.py`
  and the `contact_sync_available` flag will not be set (the button hides).

---

## Where the button lives (two places)

| Page                                    | Scope                             | Contact prefix              |
| --------------------------------------- | --------------------------------- | --------------------------- |
| `/regions/<slug>/officers/`             | Region officers (R/VR/T/S/CS)     | `X-R Franklin Ventura`      |
| `/forms/national-officer/`              | All current national officers     | `NAT-RD Franklin Ventura`   |

National officers use the initials of every significant word in their role
name (skipping "and" / "of" / "the" / "for" / "to" / "a" / "an" / "on"):

| Role                                       | Abbreviation |
| ------------------------------------------ | ------------ |
| Regional Director                          | `RD`         |
| National Officer                           | `NO`         |
| Grand Regent                               | `GR`         |
| Grand Vice Regent                          | `GVR`        |
| Grand Inner Guard                          | `GID`        |
| Grand Outer Guard                          | `GOG`        |
| Council Delegate                           | `CD`         |
| Educational Foundation Board of Director   | `EFBD`       |

`grand inner guard` and `grand outer guard` are hand-overridden in
`_ROLE_ABBR_OVERRIDES` to avoid a visual collision (both would otherwise
produce `GIG`/`GOG`).

---

## Weekly auto-sync

The dialog has a **Keep in sync automatically** checkbox next to each
provider. Toggling it POSTs to `/<provider>/auto-sync/` and stores the
selected scope in `UserContactSyncToken.auto_sync_scopes` (a Postgres
ArrayField). Users can enable auto-sync for any number of scopes per
provider (e.g. one national officer might auto-sync `national` AND their
own region — both will run once a week).

### Cron / Celery beat integration

A management command drives the actual work — safe to schedule from cron,
PythonAnywhere, or Celery beat:

```sh
# Once a week (e.g. Sunday 06:00) — from a cron-style scheduler:
podman exec thetataucmt_local_django python manage.py weekly_contact_sync
```

Options:

- `--user someone@example.com` — only sync one user's tokens (handy for
  debugging).
- `--provider google` — only sync one provider.
- `--dry-run` — print what would happen without actually pushing.

The command:
1. Loads every `UserContactSyncToken` with a non-empty `auto_sync_scopes`.
2. Skips tokens whose provider is not configured on the server.
3. Refreshes access tokens whose `expires_at` is past.
4. Calls `provider.push_contacts(token, contacts)` for each scope.
5. Records success (`last_synced_at`, `last_sync_count`) or an error string
   (`last_error`) that surfaces in the modal on the next page load.

There is also a Celery shared_task wrapper in
`thetatauCMT/contact_sync/tasks.py` (mirroring the pattern used elsewhere in
the app) — the real work still lives in the management command so
PythonAnywhere-style deployments without a broker can trigger it directly.

---

## Seeding sample data

For QA'ing the sync end-to-end you probably want a chunk of sample officers
already on file. Run the idempotent seed command:

```sh
podman exec thetataucmt_local_django python manage.py seed_contact_sync_examples
```

For each active chapter it ensures five current officers — one per role
(R/VR/T/S/CS). For the national scope, it ensures one officer per role in
COUNCIL + NATIONAL_OFFICER. Every seeded user has **both** `email` and
`email_school` populated so you can visually confirm both addresses get
pushed. Seed rows are tagged with the email suffix
`@contact-sync-seed.thetatau.local` — grep for that to identify or filter
them. The command **never deletes data** (per the natoff request); re-runs
just update fields on the existing seed rows.

Command options:

- `--chapters N` — limit to the first N active chapters (0 = all).
- `--skip-chapters` — only seed national officers.
- `--skip-national` — only seed chapter officers.

---

## Where the code lives

- `thetatauCMT/contact_sync/officers.py` — collects officer records for
  region + national scopes (`collect_contacts_for_scope`).
- `thetatauCMT/contact_sync/vcard.py` — RFC 6350 vCard 3.0 renderer.
- `thetatauCMT/contact_sync/providers/` — Google / Microsoft OAuth + push code.
- `thetatauCMT/contact_sync/models.py` — encrypted-at-rest OAuth token model +
  `auto_sync_scopes` ArrayField.
- `thetatauCMT/contact_sync/context.py` — shared template-context builder
  used by both the region and natoff pages.
- `thetatauCMT/contact_sync/views.py` — the HTTP endpoints.
- `thetatauCMT/contact_sync/tasks.py` — Celery shared_task wrapper.
- `thetatauCMT/contact_sync/management/commands/weekly_contact_sync.py`
  — the scheduled push.
- `thetatauCMT/contact_sync/management/commands/seed_contact_sync_examples.py`
  — sample data for QA.
- `thetatauCMT/templates/contact_sync/sync_modal.html` — the modal dialog.
- `thetatauCMT/templates/regions/officer_list.html` — button on region page.
- `thetatauCMT/templates/forms/officer_national.html` — button on the natoff
  form page.
- Tests: `thetatauCMT/contact_sync/tests/`.
