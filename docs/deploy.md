Deploy
========

Canonical production host is **PythonAnywhere** (mod_wsgi), settings module
`config.settings.production`. A Docker `compose/production/` stack (Traefik +
gunicorn + Postgres) also exists but is **advisory / not the live path**.

> This runbook was rewritten to cover every deployment-relevant change through
> the July 2026 release: the new apps (`events`, `attendance`, `nominations`,
> `awards`, `contact_sync`, `email_tracking`, `jobs` moderation), their settings,
> the `configs.Config` key/value + feature-flag stores, and every fixture that
> must be loaded. Companion docs: [install.md](install.md) (local/dev),
> [update.md](update.md), [contact_sync_setup.md](contact_sync_setup.md),
> [email_tracking_setup.md](email_tracking_setup.md),
> [management_commands.md](management_commands.md). The machine-readable
> environment contract lives in [`.env.example`](../.env.example).

Contents
--------
1. [Stack & what runs where](#1-stack--what-runs-where)
2. [First-time (fresh) deployment](#2-first-time-fresh-deployment)
3. [Environment variables (complete reference)](#3-environment-variables-complete-reference)
4. [Seed data / `loaddata` (complete reference)](#4-seed-data--loaddata-complete-reference)
5. [`configs.Config` keys & feature flags (post-deploy)](#5-configsconfig-keys--feature-flags-post-deploy)
6. [Integrations to wire up (Mailjet webhook, OAuth, Open edX)](#6-integrations-to-wire-up)
7. [Scheduled tasks (PythonAnywhere daily)](#7-scheduled-tasks-pythonanywhere-daily)
8. [Updating an existing deploy](#8-updating-an-existing-deploy)
9. [Backups & tested restore](#9-backups--tested-restore)
10. [Pre-deploy checklist](#10-pre-deploy-checklist)
11. [SSL certificates](#11-ssl-certificates)

---

## 1. Stack & what runs where

- **Django 4.2.x** on **Python 3.13** (PythonAnywhere) / 3.13-slim (local Docker).
- **PostgreSQL 12** (production server version).
- **Redis** cache (`django-redis`, `IGNORE_EXCEPTIONS=True`).
- **django-allauth 65.x** (email login + Google social) with **allauth-2fa /
  django-otp** (superuser 2FA is enforced).
- **django-viewflow 1.11** powers every approval workflow (disciplinary,
  premature alumnus, OSM, volunteer nomination, award nomination, …).
- **Mailjet** for email (via **django-anymail** `TrackingMailjetBackend`), with
  native open/click tracking surfaced by the `email_tracking` app.
- **Google Cloud Storage** for user media (`django-storages`); **WhiteNoise**
  compressed-manifest for static files.
- **Rollbar** for error monitoring.

Local apps that ship models/migrations (all in `LOCAL_APPS`): `users`,
`chapters`, `jobs`, `events`, `regions`, `scores`, `submissions`, `forms`,
`tasks`, `finances`, `ballots`, `surveys`, `announcements`, `notes`,
`objectives`, `trainings`, `configs`, `contact_sync`, `attendance`,
`nominations`, `awards`, `email_tracking`.

---

## 2. First-time (fresh) deployment

PythonAnywhere streamlines a lot of this — see the upstream
[Deploying an existing Django project](https://help.pythonanywhere.com/pages/DeployExistingDjangoProject/)
guide.

### 2.1 Get the code & virtualenv

```bash
git clone https://github.com/VenturaFranklin/thetatauCMT.git
# On PythonAnywhere: create the virtualenv, then in the app directory run
# `setvirtualenvproject` with no arguments.
```

### 2.2 Install requirements

Always use the production layer:

```bash
pip install -r requirements/production.txt
```

### 2.3 Create the database

From <https://help.pythonanywhere.com/pages/PostgresGettingStarted/>:

```sql
CREATE DATABASE myappdb;
CREATE USER myappuser WITH PASSWORD 'a-nice-random-password';
ALTER ROLE myappuser SET client_encoding TO 'utf8';
ALTER ROLE myappuser SET default_transaction_isolation TO 'read committed';
ALTER ROLE myappuser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE myappdb TO myappuser;
```

### 2.4 Set environment variables

Populate the virtualenv `postactivate` file **and** the WSGI file with the
variables in [§3](#3-environment-variables-complete-reference). Their canonical
locations on the live host are:

    - /home/Venturafranklin/.virtualenvs/thetatauCMT/bin/postactivate
    - files/var/www/cmt_thetatau_info_wsgi.py

Then confirm the settings module and run the deploy check:

```bash
python -c "import os; print(os.environ.get('DJANGO_SETTINGS_MODULE'))"
# MUST print: config.settings.production   (never 'staging' — staging hijacks
# all outgoing email via django-email-bandit)
python manage.py check --deploy
```

### 2.5 Add the secret / credential files

The `secrets/` directory is git-ignored; copy in:

- `secrets/GOOGLE_API_KEY` — plain-text Google Maps/Places API key (fallback if
  the `GOOGLE_API_KEY` env var is unset).
- `secrets/chaptermanagementtool-e11151065a69.json` — Google Cloud service
  account for GCS media storage + backups (path also settable via
  `GOOGLE_APPLICATION_CREDENTIALS`).

### 2.6 Migrate, seed, collect static

For a **brand-new** database you can run the all-in-one reset (it **flushes**,
so never point it at a populated DB):

```bash
python manage.py dbreset    # flush → migrate → collectstatic → createsuperuser → dbseed
```

Or run the steps individually (preferred when a DB already exists):

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser        # first admin (grant natoff group after)
python manage.py dbseed                 # loads the 8 core fixtures + task_dates
```

Then load the fixtures `dbseed` does **not** cover (see
[§4](#4-seed-data--loaddata-complete-reference) for why):

```bash
python manage.py loaddata national_region   # regions.Region "National" (pk 1)
python manage.py loaddata award_types        # 30 awards.AwardType rows (Awards feature)
python manage.py loaddata keywords           # ~1000 jobs.Keyword rows (Job Board autocomplete)
```

### 2.7 Post-deploy configuration

- Set the `configs.Config` reviewer/assignment keys and confirm feature flags —
  see [§5](#5-configsconfig-keys--feature-flags-post-deploy).
- Register the Mailjet tracking webhook and (optionally) OAuth apps — see
  [§6](#6-integrations-to-wire-up).
- In Django admin add the Google **Social Application**
  (`/admin/socialaccount/socialapp/`) and attach the correct Site.
- Configure the [scheduled tasks](#7-scheduled-tasks-pythonanywhere-daily).

---

## 3. Environment variables (complete reference)

Set these in the virtualenv `postactivate` and mirror them in the WSGI file.
Variables marked **required** have **no default** in `config.settings.production`
— a missing value fails fast at startup (by design). `.env.example` is the
authoritative template.

### 3.1 Core Django

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DJANGO_SETTINGS_MODULE` | ✅ | — | Must be `config.settings.production`. |
| `DJANGO_SECRET_KEY` | ✅ | — | 50+ char random. <https://www.miniwebtool.com/django-secret-key-generator/> |
| `DJANGO_DEBUG` | — | `False` | Never `True` in prod. |
| `DJANGO_ALLOWED_HOSTS` | — | `cmt.thetatau.org,cmt.thetatau.info` | Comma-separated. |
| `DJANGO_ADMIN_URL` | ✅ | — | Unguessable admin path, e.g. `s0me-secret-admin/` (trailing slash). |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | — | `https://cmt.thetatau.org,https://cmt.thetatau.info` | **New.** Django 4.x requires scheme. |
| `DJANGO_SECURE_HSTS_SECONDS` | — | `31536000` | **New.** 1 year (preload-eligible). |
| `DJANGO_SECURE_SSL_REDIRECT` | — | `True` | |
| `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` | — | `True` | |
| `DJANGO_SECURE_HSTS_PRELOAD` | — | `True` | |
| `DJANGO_SECURE_CONTENT_TYPE_NOSNIFF` | — | `True` | |
| `DJANGO_ACCOUNT_ALLOW_REGISTRATION` | — | `False` | allauth open registration. |
| `DJANGO_READ_DOT_ENV_FILE` | — | `True` | Read a `.env` file (OS env still wins). |
| `WEB_CONCURRENCY` | — | `4` | Worker count. |

### 3.2 Database & cache

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | `postgres://user:pass@host:port/dbname` |
| `CONN_MAX_AGE` | — | `60` | Persistent DB connections (seconds). |
| `REDIS_URL` | — | `redis://127.0.0.1:6379` | Cache backend. |

### 3.3 Email — Mailjet / Anymail

| Variable | Required | Default | Notes |
|---|---|---|---|
| `MAILJET_API_KEY` | ✅ | — | Anymail public key. |
| `MAILJET_SECRET_KEY` | ✅ | — | Anymail private key. |
| `DJANGO_EMAIL_LIVE` | — | `True` | When true, prod uses `core.email.TrackingMailjetBackend`. |
| `ANYMAIL_WEBHOOK_SECRET` | — | `""` | **New.** `user:pass` basic-auth securing the Mailjet tracking webhook. |
| `EMAIL_TRACK_OPENS` | — | `True` | **New.** Mailjet native open tracking. |
| `EMAIL_TRACK_CLICKS` | — | `True` | **New.** Mailjet native click tracking. |
| `DJANGO_DEFAULT_FROM_EMAIL` | — | `Theta Tau … <cmt@thetatau.org>` | |
| `DJANGO_SERVER_EMAIL` | — | = default from | |
| `DJANGO_EMAIL_SUBJECT_PREFIX` | — | `[CMT]` | |

### 3.4 Captcha

| Variable | Required | Default | Notes |
|---|---|---|---|
| `RECAPTCHA_PUBLIC_KEY` | ✅ | — | |
| `RECAPTCHA_PRIVATE_KEY` | ✅ | — | |
| `HCAPTCHA_SITEKEY` | ✅ | — | |
| `HCAPTCHA_SECRET` | ✅ | — | |
| `BYPASS_CAPTCHA` | — | `False` | **New.** Disables all captchas (debug/testing only — leave `False` in prod). |

### 3.5 Google Cloud (storage + APIs)

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DJANGO_GCP_STORAGE_BUCKET_NAME` | ✅ | — | GCS bucket for media. |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | `secrets/chaptermanagementtool-…json` | Service-account path. |
| `GOOGLE_API_KEY` | — | `TESTING` → `secrets/GOOGLE_API_KEY` | Maps/Places for the address widget. |

### 3.6 Error monitoring

| Variable | Required | Default | Notes |
|---|---|---|---|
| `ROLLBAR_ACCESS` | — | `""` | Rollbar server access token. |

### 3.7 Contact sync (region/national officer → Google/Microsoft) — **New**

Each provider only appears in the UI when **both** its client id and secret are
set. The vCard download path always works without any of these. Full setup:
[contact_sync_setup.md](contact_sync_setup.md).

| Variable | Default | Notes |
|---|---|---|
| `CONTACT_SYNC_GOOGLE_CLIENT_ID` | `""` | Google OAuth client id (People API). |
| `CONTACT_SYNC_GOOGLE_CLIENT_SECRET` | `""` | |
| `CONTACT_SYNC_MICROSOFT_CLIENT_ID` | `""` | Microsoft/Graph OAuth client id. |
| `CONTACT_SYNC_MICROSOFT_CLIENT_SECRET` | `""` | |
| `CONTACT_SYNC_MICROSOFT_TENANT` | `common` | `common`/`organizations`/`consumers`/tenant GUID. |

### 3.8 Feature settings — **New**

| Variable | Default | Notes |
|---|---|---|
| `EVENTS_AUTO_APPROVE_NATIONAL_PUBLIC` | `True` | Auto-approve public events created by National Officers. |
| `ATTENDANCE_QUORUM_RULE` | `majority` | `majority` / `two_thirds` / a float `0<x<=1`. |
| `ATTENDANCE_GUEST_SEARCH_MIN_LENGTH` | `2` | Min chars for guest autocomplete. |
| `ATTENDANCE_GUEST_SEARCH_MAX_RESULTS` | `20` | Max guest autocomplete results. |
| `ATTENDANCE_MATCH_AUTO_ACCEPT_THRESHOLD` | `0.60` | Auto-match confidence for national-event uploads. |
| `AWARDS_SHOW_REVOKED` | `False` | Show revoked awards (separate section) on public profiles. |
| `NOMINATION_CONSENT_TOKEN_MAX_AGE_DAYS` | `30` | Expiry for tokenized nominee-consent links. |
| `NOMINATION_TRAINING_PROVIDER` | (unset) | Dotted path to a custom training-completion provider. |

### 3.9 Open edX / LMS integration

| Variable | Default | Notes |
|---|---|---|
| `LMS_ID` | `None` | LMS OAuth client id. |
| `LMS_SECRET` | `None` | LMS OAuth secret. |
| `ED_ID` | `None` | Open edX OAuth client id. |
| `ED_SECRET` | `None` | Open edX OAuth secret. |
| `ED_HOST` | `https://ed.thetatau.org` | Open edX base URL. |
| `ED_COURSES` | `course-v1:ThetaTau+TT101+intro` | Comma-separated course run(s) to enroll everyone in. |

### 3.10 Other integrations & people

| Variable | Default | Notes |
|---|---|---|
| `MAILERLITE_API_KEY` | `""` | **New.** MailerLite subscriber activity on the member-communication page. |
| `MOOSEND_API_KEY` | `None` | Optional. |
| `METABASE_SECRET_KEY` | `None` | Optional dashboards. |
| `EXECUTIVE_DIRECTOR` | `Jim.Gaffney@thetatau.org` | `User.username` of the ED; fallback reviewer/recipient for workflows. |

### 3.11 Backups (dbbackup)

| Variable | Default | Notes |
|---|---|---|
| `DBBACKUP_LOCAL` | `True` | `True` = local filesystem; `False` = GCS bucket `theta-tau-database`. |
| `DBBACKUP_STORAGE_LOCATION` | `database_backups` | Local backup directory (when `DBBACKUP_LOCAL`). |

---

## 4. Seed data / `loaddata` (complete reference)

Two management commands drive seeding:

- **`dbreset`** = `flush` → `migrate` → `collectstatic` → `createsuperuser` →
  `dbseed`. **Destructive** (`flush` wipes data) — fresh installs only.
- **`dbseed`** loads the eight core fixtures **in this order**, then generates
  the current academic year's task dates:

  | # | Command | Provides |
  |---|---|---|
  | 1 | `loaddata scoretypes` | `scores.ScoreType` catalog |
  | 2 | `loaddata tasks` | `tasks.Task` definitions |
  | 3 | `loaddata badges` | `forms.Badge` catalog |
  | 4 | `loaddata chapters` | `chapters.Chapter` roster |
  | 5 | `loaddata groups` | `users` auth Groups (natoff, officer, …) |
  | 6 | `loaddata country` | `jobs.Country` list |
  | 7 | `loaddata feature_flags` | `configs.Config` feature-flag rows |
  | 8 | `loaddata default_configs` | `configs.Config` assignment/setting rows |
  | — | `task_dates --current-year` | Materializes this year's `tasks.TaskDate` rows |

### 4.1 Fixtures NOT loaded by `dbseed` (load manually)

These are **not** in `dbseed` and are **not** applied by any migration, so a
fresh install (and the first deploy that enables the July features) must load
them explicitly:

```bash
python manage.py loaddata national_region   # regions/fixtures/national_region.json
python manage.py loaddata award_types        # awards/fixtures/award_types.json
python manage.py loaddata keywords           # jobs/fixtures/keywords.json
```

| Fixture | Rows | Why it matters | Idempotency |
|---|---|---|---|
| `national_region` | 1 | The `National` region (pk 1) that national events/officers hang off. | Fixed pk 1 → re-load overwrites pk 1 only. On an existing DB, confirm pk 1 is already "National" before loading. |
| `award_types` | 30 | The Awards catalog (`AwardType`). The Awards feature is **non-functional without it** (no award types to nominate/grant). | Fixed pks 1–30 → re-load overwrites those rows in place (safe/idempotent). |
| `keywords` | ~1000 | Job Board keyword autocomplete. | Fixed pks → re-load overwrites in place. |

> **Fixture idempotency note.** `feature_flags` uses `"pk": null` (auto id) so it
> is **not** idempotent — re-running duplicates rows (harmless; the flag reader
> uses the latest row). `default_configs` also uses `"pk": null`. The three
> fixtures above use fixed pks and are safe to re-load. When in doubt on a
> populated prod DB, set only the missing `Config` keys via the admin instead of
> re-loading.

### 4.2 Do NOT run seed/demo commands in production

These generate throwaway sample data and are guarded by `core.seed_guard`
(they refuse to run when `DEBUG=False` unless `--force` is passed). **Never**
wire any of them into a scheduled task:
`seed_awards_demo`, `seed_rollbook_qa`, `seed_contact_sync_examples`,
`seed_dashboard_data`, `seed_pending_national_events`.

---

## 5. `configs.Config` keys & feature flags (post-deploy)

The app uses a live-editable `configs.Config` key/value store (Django admin →
**Configs**). `dbseed` seeds discoverable rows (blank value + description) from
`default_configs.json` and `feature_flags.json`; set the real values in the
admin — **no redeploy needed**.

### 5.1 Assignment / reviewer keys (`default_configs.json`)

Each accepts a **username**, an **email**, or a **national-officer role name**
(e.g. `grand regent`). Blank falls back to `CentralOffice`, then
`settings.EXECUTIVE_DIRECTOR`.

| Key | Purpose |
|---|---|
| `VolunteerReviewer` | Volunteer Nomination: initial reviewer. |
| `VettingReviewer` | Volunteer Nomination: vetting / reference check. |
| `Interviewer` | Volunteer Nomination: interview. |
| `TrainingAdministrator` | Volunteer Nomination: marks required training (CMT LMS + Vector). |
| `Confirmer` | Volunteer Nomination: confirms before appointment. |
| `AppointmentProcessor` | Volunteer Nomination: final appointment. |
| `CentralOffice` | Default reviewer/denial actor fallback. |
| `AwardApprover` | Award nomination approver. |
| `HSEducationReviewer` | Health & Safety education submission reviewer. |

### 5.2 Setting keys (`default_configs.json`)

| Key | Default | Purpose |
|---|---|---|
| `follow_up_interval_months` | `6` | Volunteer-nomination re-contact cadence (months). |
| `GraduationSurvey` | `""` | `surveys.Survey` slug sent to graduating members. |
| `PreAlumnSurvey` | `""` | `surveys.Survey` slug for premature-alumnus members. |
| `ChapterMinimum` | `""` | Minimum active-member count for chapter status calcs. |
| `GROUP_TAX_FORM` | `""` | URL of the group tax-exemption form on the chapter page. |
| `PledgeWelcome` | `""` | HTML welcome copy included in the pledge welcome email. |
| `JOBS_CREATION_EMAIL` | `""` | Recipient list notified on new job postings (whitespace/comma/semicolon separated). |

### 5.3 Feature flags (`feature_flags.json`)

Live on/off toggles (`configs.Config`). Any value in
`{0,false,no,off,disabled,hide,hidden}` disables; anything else (e.g. `on`)
enables. Direct URLs are intentionally **not** blocked — flags only hide UI.

| Key | Default | Hides |
|---|---|---|
| `FEATURE_AWARDS` | `on` | Awards directory, nominations, and award cards/badges. |
| `FEATURE_JOBS` | `on` | Job Board link. |
| `FEATURE_EVENTS_CALENDAR` | `on` | Events Calendar menu item + calendar icon. |

---

## 6. Integrations to wire up

### 6.1 Mailjet tracking webhook (email open/click) — **New**

The `email_tracking` app records opens/clicks from Mailjet events delivered to
Anymail at `/anymail/mailjet/tracking/`. Register the callback URL once (uses the
same `MAILJET_*` keys). Secure it by setting `ANYMAIL_WEBHOOK_SECRET` and using
the same `user:pass` in the URL.

```bash
python manage.py register_mailjet_webhook --list          # show current registration
python manage.py register_mailjet_webhook \
    --url https://user:pass@cmt.thetatau.org/anymail/mailjet/tracking/
```

Full walk-through: [email_tracking_setup.md](email_tracking_setup.md).

### 6.2 Contact-sync OAuth apps — **New (optional)**

Only needed for the Google/Microsoft "sync officers to my contacts" buttons. Set
the `CONTACT_SYNC_*` vars ([§3.7](#37-contact-sync-regionnational-officer--googlemicrosoft--new))
and follow [contact_sync_setup.md](contact_sync_setup.md) for the OAuth consent
screen, scopes, and redirect URIs.

### 6.3 Open edX / LMS

Set the `LMS_*` / `ED_*` vars ([§3.9](#39-open-edx--lms-integration)). Enrollment
and training sync run via the `trainings` commands
([§7](#7-scheduled-tasks-pythonanywhere-daily)).

### 6.4 Google Social Application

After the first superuser exists, add the Google provider in Django admin
(`/admin/socialaccount/socialapp/`) and attach the production Site.

---

## 7. Scheduled tasks (PythonAnywhere daily)

PythonAnywhere only offers **daily** scheduled tasks, so commands that should run
weekly/monthly **self-gate internally** (day-of-week / day-of-month). Schedule
them daily and let them decide. Use `--dry-run` / `--override` for testing only —
**never** wire those flags into the live schedule.

| Command | Effective cadence | Purpose |
|---|---|---|
| `task_dates --current-year` | daily | Ensure current academic-year task dates exist. |
| `archive_old_task_dates` | daily | Retire stale `TaskDate` rows. |
| `set_current_status_roles` | daily | Recompute members' current status/roles. |
| `officer_update_reminder_email` | daily | Chapter officer-update reminders. |
| `region_officer_reminder_digest` | daily → sends **Mon** | Weekly RD officer digest (`--weekday 0`). |
| `monthly_chapter_officer_email` | daily → sends **1st** | Monthly per-region chapter health dashboard. |
| `grad_anniversary_email` | daily | Graduation-anniversary emails (respects unsubscribes). |
| `award_digest` | daily → sends **1st** | Monthly award-grant digest. |
| `nomination_follow_up` | daily | Re-contact volunteer nominees per `follow_up_interval_months`. |
| `job_search_notify --frequency both` | daily | Job Board saved-search alerts (daily + weekly digests). |
| `weekly_contact_sync` | daily | Push auto-sync-enrolled contact lists. |
| `remind_workflow_tasks` | daily | Viewflow task reminders. |
| `discipline_tasks` | daily | Disciplinary-process follow-ups. |
| `badge_pnm_notify` | daily | Badge/PNM notifications. |
| `sync_trainings` / `enroll_all_ed` | daily | Open edX training sync + enrollment. |
| `sync_quickbooks` | daily | Finances sync. |

> This is the deployment-relevant set; confirm the exact crontab against the live
> PythonAnywhere **Tasks** page. Every command above is idempotent and safe to
> run daily.

---

## 8. Updating an existing deploy

```bash
# (optional) enable maintenance mode
nano maintenance_active

workon thetatauCMT
git pull origin master
pip install -r requirements/production.txt      # if requirements changed

python manage.py showmigrations | grep '\[ \]'  # review pending (additive/safe)
python manage.py migrate
python manage.py collectstatic --noinput

# Only if new seed rows are needed this release:
#   python manage.py loaddata award_types      # e.g. new award types
#   (or set the new Config keys in the admin)

python manage.py check --deploy                 # resolve anything reported
# reload the web app (PythonAnywhere "Reload" button), then remove maintenance_active
```

When upgrading **into** the July release for the first time, also run the
one-time fixtures in [§4.1](#41-fixtures-not-loaded-by-dbseed-load-manually)
(`national_region`, `award_types`, `keywords`) and set the new `Config` keys /
confirm feature flags in [§5](#5-configsconfig-keys--feature-flags-post-deploy),
then register the Mailjet webhook ([§6.1](#61-mailjet-tracking-webhook-email-openclick--new)).

---

## 9. Backups & tested restore

Backups run via **django-dbbackup** (`backup.sh`). A backup is only useful once a
restore has been proven, so verify a restore into a **throwaway** database (never
the live DB):

```bash
python manage.py dbbackup       # create a fresh backup
python manage.py listbackups    # list available backups
# Point DATABASE_URL at a scratch DB, then:
python manage.py dbrestore      # restore latest; sanity-check row counts / a login
```

Record the date of the last successful **restore test** in the deploy log.

---

## 10. Pre-deploy checklist

1. **Settings module** = `config.settings.production` in both the WSGI file and
   the virtualenv `postactivate` (never `staging`). Verify:
   `python -c "import os; print(os.environ.get('DJANGO_SETTINGS_MODULE'))"`.
2. **Env vars** present — especially the required (no-default) ones in
   [§3](#3-environment-variables-complete-reference) and any **new** vars this
   release. Run `python manage.py check --deploy` and resolve everything.
3. **Migrations** applied: `showmigrations` → `migrate` (additive/safe).
4. **Seed data**: `dbseed` for core fixtures; load the extra fixtures in
   [§4.1](#41-fixtures-not-loaded-by-dbseed-load-manually) if this is a fresh
   install or a first-time feature enablement.
5. **Config keys & feature flags** reviewed in the admin
   ([§5](#5-configsconfig-keys--feature-flags-post-deploy)).
6. **Static files**: `collectstatic --noinput`.
7. **Integrations**: Mailjet webhook registered; OAuth/Open edX configured if used.
8. **Scheduled tasks** present on the PythonAnywhere Tasks page
   ([§7](#7-scheduled-tasks-pythonanywhere-daily)); no `seed_*` command scheduled.
9. **Backups**: fresh backup taken and a **restore** tested into a scratch DB.
10. **Dependency audit**: review CI `pip-audit` output; patch high/critical.

---

## 11. SSL certificates

PythonAnywhere Let's Encrypt: <https://help.pythonanywhere.com/pages/LetsEncrypt/>

Check expiry:

```bash
openssl x509 -enddate -noout -in ~/letsencrypt/cmt.thetatau.org/cert.pem
```

Renew:

```bash
cd ~/letsencrypt
~/dehydrated/dehydrated --cron --domain cmt.thetatau.org --out . --challenge http-01
```

---

### Appendix — WSGI file template

The live PythonAnywhere WSGI file sets the same variables as `postactivate`
(secrets redacted). Keep the two in sync:

```python
import os
import sys

path = "/home/Venturafranklin/thetatauCMT"
if path not in sys.path:
    sys.path.append(path)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.production"
os.environ["DJANGO_SECRET_KEY"] = ""
os.environ["DJANGO_ALLOWED_HOSTS"] = "cmt.thetatau.org,cmt.thetatau.info"
os.environ["DJANGO_ADMIN_URL"] = ""
os.environ["DJANGO_CSRF_TRUSTED_ORIGINS"] = "https://cmt.thetatau.org,https://cmt.thetatau.info"
os.environ["DATABASE_URL"] = ""
os.environ["MAILJET_API_KEY"] = ""
os.environ["MAILJET_SECRET_KEY"] = ""
os.environ["ANYMAIL_WEBHOOK_SECRET"] = ""
os.environ["RECAPTCHA_PUBLIC_KEY"] = ""
os.environ["RECAPTCHA_PRIVATE_KEY"] = ""
os.environ["HCAPTCHA_SITEKEY"] = ""
os.environ["HCAPTCHA_SECRET"] = ""
os.environ["DJANGO_GCP_STORAGE_BUCKET_NAME"] = ""
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""
os.environ["ROLLBAR_ACCESS"] = ""
# Optional / feature-specific (see §3): MAILERLITE_API_KEY, CONTACT_SYNC_*,
# LMS_*, ED_*, EXECUTIVE_DIRECTOR, EVENTS_AUTO_APPROVE_NATIONAL_PUBLIC, etc.

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

