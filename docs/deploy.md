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
>
> The October 2026 Transition Reports release has its own upgrade steps in
> [§8.1](#81-upgrading-into-the-transition-reports-release-october-2026).

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
`nominations`, `awards`, `email_tracking`, `guides`.

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
CREATE USER myappuser WITH PASSWORD 'EXAMPLE_PASSWORD';  -- generate a real random one
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
python manage.py loaddata award_eligibility_rules  # 51 awards.EligibilityRule rows (after award_types)
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
| `DATABASE_URL` | ✅ | — | `postgres://EXAMPLE_USER:EXAMPLE_PASSWORD@host:port/dbname` |
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
| `GUARDIAN_EMAIL` | — | Admin login for the Guardian Conduct System; required by the `sync_guardian` scheduled command ([§7](#7-scheduled-tasks-pythonanywhere-daily)). |
| `GUARDIAN_PASSWORD` | — | Password for `GUARDIAN_EMAIL`. |

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
python manage.py loaddata award_eligibility_rules  # awards/fixtures/award_eligibility_rules.json
python manage.py loaddata keywords           # jobs/fixtures/keywords.json
```

| Fixture | Rows | Why it matters | Idempotency |
|---|---|---|---|
| `national_region` | 1 | The `National` region (pk 1) that national events/officers hang off. | Fixed pk 1 → re-load overwrites pk 1 only. On an existing DB, confirm pk 1 is already "National" before loading. |
| `award_types` | 30 | The Awards catalog (`AwardType`). The Awards feature is **non-functional without it** (no award types to nominate/grant). | Fixed pks 1–30 → re-load overwrites those rows in place (safe/idempotent). |
| `award_eligibility_rules` | 51 | Baseline `EligibilityRule` rows for the 30 award types (recipient-kind guard per award, plus member-status filters). Without them every award is open to every member. Requires `award_types` first (the fixture links rules to awards **by award name**, via natural keys). | `"pk": null` + natural key `(award name, rule_type, member_status, hook_key)` → re-load updates the matching row in place instead of duplicating, and never clobbers rules natoffs added in the admin. |
| `keywords` | ~1000 | Job Board keyword autocomplete. | Fixed pks → re-load overwrites in place. |

> **Fixture idempotency note.** `feature_flags` uses `"pk": null` (auto id) so it
> is **not** idempotent: re-running duplicates rows. That is harmless only on a
> fresh DB. `Config.get_value` reads the newest row, so on a configured prod DB the
> reloaded rows (`on` for flags, blank for `default_configs`) override whatever an
> admin already set. `default_configs` also uses `"pk": null`. The three
> fixtures above use fixed pks and are safe to re-load. On a populated prod DB,
> never re-run `dbseed` or those two fixtures; set only the missing `Config` keys
> via the admin instead.

### 4.2 Do NOT run seed/demo commands in production

These generate throwaway sample data and are guarded by `core.seed_guard`
(they refuse to run when `DEBUG=False` unless `--force` is passed). **Never**
wire any of them into a scheduled task:
`seed_awards_demo`, `seed_rollbook_qa`, `seed_contact_sync_examples`,
`seed_dashboard_data`, `seed_pending_national_events`,
`seed_transition_reports_demo`, `seed_big_little_demo`.

The exception is `seed_transition_prompt_set` and `seed_transition_tags`: they
load real production data and are meant to be run once
([§8.1](#81-upgrading-into-the-transition-reports-release-october-2026)).

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
| `BIG_LITTLE_MANAGER_ROLES` | `pledge/new member educator` | Roles that may record, change and remove anyone's Big for their chapter and upload a CSV of pairings, besides the chapter officers. Comma-separated role names as they appear on officer records. Missing or blank means the New Member Educator only. |

### 5.3 Feature flags (`feature_flags.json`)

Live on/off toggles (`configs.Config`). Any value in
`{0,false,no,off,disabled,hide,hidden}` disables; anything else (e.g. `on`)
enables. Direct URLs are intentionally **not** blocked — flags only hide UI.

| Key | Default | Hides |
|---|---|---|
| `FEATURE_AWARDS` | `on` | Awards directory, nominations, and award cards/badges. |
| `FEATURE_JOBS` | `on` | Job Board link. |
| `FEATURE_EVENTS_CALENDAR` | `on` | Events Calendar menu item + calendar icon. |

### 5.4 Transition Reports keys

Seeded as discoverable rows by `default_configs.json` (the first four) and
`feature_flags.json` (the three `*_ENABLED` flags). All are optional: when a key is
missing, the default shown here applies.

| Key | Default | Purpose |
|---|---|---|
| `TRANSITIONS_DUE_DATE_OFFSET_DAYS` | `14` | Days before an officer's term end that their report is due. |
| `TRANSITIONS_REMINDER_OFFSETS_DAYS` | `21,14,7,1,-1,-7,-14` | Reminder offsets in days relative to the due date (positive before, negative after). The most negative one is the last reminder. |
| `TRANSITIONS_SEASONAL_REMINDER_OFFSET_DAYS` | `30` | Days before the current semester ends to send the once-per-semester reminder to everyone with an open report. |
| `TRANSITIONS_RD_ESCALATION_OFFSET_DAYS` | `-7` | Once a reminder offset at or below this is reached, the Regional Director is added to the email (the chapter Regent is added once the report is past due). |
| `TRANSITIONS_COUNCIL_ENABLED` | `on` | `off` removes Council positions (grand regent, grand scribe, and so on) from Transition Reports. |
| `TRANSITIONS_NATIONAL_OFFICER_ENABLED` | `on` | `off` removes National Officer positions from Transition Reports. |
| `TRANSITIONS_COMMITTEE_CHAIR_ENABLED` | `on` | `off` removes Committee Chair positions from Transition Reports. |

Regent, vice regent, scribe, treasurer, corresponding secretary, pledge/new member
educator and risk management chair are always required and are not controlled by
any flag. The other three types are optional reports when enabled. The flags and
the per-position override (Django admin → Transitions → **Position Overrides**:
required, optional or excluded, which beats the type flag) only stop **new**
obligations being generated. Ones already created stay, so set them before the
first `generate_transition_obligations` run
([§8.1](#81-upgrading-into-the-transition-reports-release-october-2026)).
**Start report** on the Transition Reports page creates an obligation too (the same
one the daily command would), so the flags and overrides apply to it as well.
`TRANSITIONS_SEASONAL_REMINDER_LAST_SENT_FOR` is written by the system to record the
last semester end it broadcast for; do not create, edit or delete it.

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
    --url https://EXAMPLE_USER:EXAMPLE_PASSWORD@cmt.thetatau.org/anymail/mailjet/tracking/
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
| `prune_acknowledgements` | daily | Prune stale guides/What's New acknowledgement rows (`--days`, default 365). |
| `set_current_status_roles` | daily | Recompute members' current status/roles. |
| `member_update_process` | daily | Continue parked Member Update Process tasks 7 days after submission. |
| `officer_update_reminder_email` | daily | Chapter officer-update reminders. |
| `region_officer_reminder_digest` | daily → sends **Mon** | Weekly RD officer digest (`--weekday 0`). |
| `ballot_reminders` | daily → per-ballot 7 day ladder | Re-sends an open ballot every 7 days to whoever has not voted, widening the chapter copy list at day 14 (all officers) and day 21 (chapter roles + Regional Director), plus a final reminder on the due date. Voting closes 5pm Pacific on the due date. |
| `monthly_chapter_officer_email` | daily → sends **1st** | Monthly per-region chapter health dashboard. |
| `grad_anniversary_email` | daily | Graduation-anniversary emails (respects unsubscribes). |
| `chapter_founding_day_email` | daily | Chapter founding-anniversary emails to initiated members. |
| `chapter_pledges_check` | daily → sends **Mon** | Warn chapter e-board of pledges not initiated after 6 months. |
| `award_digest` | daily → sends **1st** | Monthly award-grant digest. |
| `nomination_follow_up` | daily | Re-contact volunteer nominees per `follow_up_interval_months`. |
| `ballot_reminders` | daily | 7 day reminder ladder for unreturned open ballots (widens the CC list as it ages). |
| `job_search_notify --frequency both` | daily → weekly digest sends **Wed** | Job Board saved-search alerts (daily digest every run, `--weekday 2`). |
| `weekly_contact_sync` | daily → pushes **Thu** | Push auto-sync-enrolled contact lists (`--weekday 3`). |
| `remind_workflow_tasks` | daily | Viewflow task reminders. |
| `discipline_tasks` | daily | Disciplinary-process follow-ups. |
| `badge_pnm_notify` | daily | Badge/PNM notifications. |
| `sync_trainings` / `enroll_all_ed` | daily | Open edX training sync + enrollment. |
| `sync_guardian` | daily → syncs **Tue** | Push the active member roster to the Guardian Conduct System (needs `GUARDIAN_EMAIL`/`GUARDIAN_PASSWORD`, [§3.10](#310-other-integrations--people)). |
| `sync_quickbooks` | daily | Finances sync. |
| `generate_transition_obligations` | daily | Create/refresh Transition Report obligations from officer term ends (looks back 365 days, ahead 45 by default, derived from the [§5.4](#54-transition-reports-keys) offsets) and mark past-due ones `missed`. Officers can also press **Start report** on `/transitions/` before their report is assigned; that creates the same obligation, which this command then reuses. Schedule it before the two below. First-run steps: [§8.1](#81-upgrading-into-the-transition-reports-release-october-2026). |
| `send_transition_report_reminders` | daily | Due-date reminder ladder (`TRANSITIONS_REMINDER_OFFSETS_DAYS`) plus the once-per-semester broadcast. **Do the first-run baseline in [§8.1](#81-upgrading-into-the-transition-reports-release-october-2026) before scheduling it.** |
| `send_transition_handoff_notices` | daily | Tells a new officeholder their predecessors' reports are available (sent only when a report exists). |

> This is the deployment-relevant set; confirm the exact crontab against the live
> PythonAnywhere **Tasks** page. Every command above is idempotent and safe to
> run daily.

---

## 8. Updating an existing deploy

```bash
# (optional) enable maintenance mode
nano maintenance_active

workon thetatauCMT
git pull origin main
pip install -r requirements/production.txt      # if requirements changed

python manage.py showmigrations | grep '\[ \]'  # review pending (additive/safe)
python manage.py migrate

# MUST print config.settings.production before collecting static -- see the
# warning below. `workon` exports it via postactivate.
python -c "import os; print(os.environ.get('DJANGO_SETTINGS_MODULE'))"
python manage.py collectstatic --noinput
python manage.py load_feature_registry          # re-sync the feature catalog (safe/idempotent, upsert by key)

# Only if new seed rows are needed this release:
#   python manage.py loaddata award_types      # e.g. new award types
#   (or set the new Config keys in the admin)

python manage.py check --deploy                 # resolve anything reported
# reload the web app (PythonAnywhere "Reload" button), then remove maintenance_active
```

> **Static files silently fail to update if the settings module is wrong.**
> `manage.py` falls back to `config.settings.local`, which uses the plain
> `StaticFilesStorage`. Production uses `CompressedManifestStaticFilesStorage`,
> which writes content-hashed filenames plus `staticfiles/staticfiles.json`, and
> `{% static %}` resolves through that manifest.
>
> Running `collectstatic` **without** `config.settings.production` copies the
> unhashed files but never rewrites the hashed copies or the manifest. Pages keep
> pointing at the previous hash, which is still on disk and is served with a
> ten-year `immutable` cache header, so the change is invisible no matter how many
> times you reload the web app or clear your browser cache.
>
> Verify after collecting, then reload the web app:
>
> ```bash
> grep -o 'project\.[a-f0-9]\{12\}\.css' staticfiles/staticfiles.json
> ```
>
> If the hash did not change when `project.css` did, collectstatic ran under the
> wrong settings. Re-run it explicitly and reload:
>
> ```bash
> python manage.py collectstatic --noinput --clear --settings=config.settings.production
> ```

> **The reload is not optional, and `--clear` makes skipping it fatal.**
> Two caches live inside the mod_wsgi process and are only rebuilt at startup:
> the staticfiles manifest (read once by the storage backend) and WhiteNoise's
> index of `STATIC_ROOT` (scanned once, because `autorefresh` is off when
> `DEBUG=False`). `collectstatic` changes nothing a visitor sees until you reload.
>
> Skip the reload after a `--clear` and the site loses all styling, because the
> old hashed file the running process is still advertising has just been deleted:
>
> | Request | Result |
> | --- | --- |
> | old hash, still emitted by the cached manifest | **500** (in WhiteNoise's index, missing on disk) |
> | new hash, present on disk | **404** (not in WhiteNoise's startup index) |
>
> The fix is only ever "reload the web app", never another `collectstatic`.
> Prefer a plain `collectstatic --noinput` for routine deploys: it writes the new
> hashed file and manifest without deleting the old one, so the window between
> collecting and reloading stays harmless. Keep `--clear` for when you actually
> need to purge accumulated hashes, and reload immediately afterwards.

> **"Missing staticfiles manifest entry for '…'" is not always a stale manifest.**
> `collectstatic` only collects what a staticfiles finder can see:
> `thetatauCMT/static/` plus the `static/` folder of each app in `INSTALLED_APPS`.
> Check the path from the error first:
>
> ```bash
> python manage.py findstatic email_signals/css/signal_change_form.min.css
> ```
>
> "No matching file found" means no `collectstatic` will ever fix it: the file is
> missing from the installed package (django-email-signals 2.0.0 shipped without
> its admin CSS/JS) or its app is not in `INSTALLED_APPS` (`tinymce`). Change the
> code that references it instead; `thetatauCMT/users/tests/test_admin_static.py`
> fails for any admin whose media points at such a file.

When upgrading **into** the July release for the first time, also run the
one-time fixtures in [§4.1](#41-fixtures-not-loaded-by-dbseed-load-manually)
(`national_region`, `award_types`, `keywords`) and set the new `Config` keys /
confirm feature flags in [§5](#5-configsconfig-keys--feature-flags-post-deploy),
then register the Mailjet webhook ([§6.1](#61-mailjet-tracking-webhook-email-openclick--new)).

### 8.1 Upgrading into the Transition Reports release (October 2026)

First production release of the `transitions` app (`main` at `f95bd44a`, the merge
of `transitions-reports`). It adds ten migrations (`transitions` 0001 to 0010, which
only create the app's own new tables), three daily commands
([§7](#7-scheduled-tasks-pythonanywhere-daily)), one static file
(`js/transitions_compose.js`), feature-catalog and role-guide entries, and seven
optional `Config` keys ([§5.4](#54-transition-reports-keys)). There are no new
required environment variables. Other work on `main` since August rides along
(migrations in `users`, `forms`, `ballots`, `tasks`, `nominations`, `awards`,
`events`, `announcements` and `guides`); `showmigrations` lists whatever is still
pending. Verified on `f95bd44a` before release: full test suite 3327 passed, 16
skipped, 0 failed; no model changes missing a migration; `check` clean.

Run the standard flow in [§8](#8-updating-an-existing-deploy) first: fresh backup
([§9](#9-backups--tested-restore)), `git pull origin main`,
`pip install -r requirements/production.txt` (the `rollbar` and `django-dbbackup`
pins changed), `migrate`, `collectstatic`, `load_feature_registry`,
`check --deploy`, then reload. Then, in this order:

**1. Check the new static file is in the manifest.**

```bash
grep -o 'transitions_compose\.[a-f0-9]\{12\}\.js' staticfiles/staticfiles.json
```

One hashed name should print. Nothing printing means `collectstatic` ran under the
wrong settings module (see the warning above).

**2. Seed the prompt set and tags (once).** Both are idempotent. Unlike the demo seeds
in [§4.2](#42-do-not-run-seeddemo-commands-in-production), they load real data and are
not guarded.

```bash
python manage.py seed_transition_prompt_set --dry-run
python manage.py seed_transition_prompt_set     # 4 templates, 44 prompts
python manage.py seed_transition_tags --dry-run
python manage.py seed_transition_tags           # regions, active chapters, 8 general tags
```

Without the prompt set, officers see "No report template is configured for this
position yet." Prompt keys are permanent once seeded, and re-running
`seed_transition_prompt_set` later overwrites prompt edits made in the admin, so run
it once and make later changes in the admin.

**3. Decide scope, before the first generate run.** The five chapter officer roles
plus pledge/new member educator and risk management chair are always required.
Council, National Officer and Committee Chair positions default to optional reports.
To launch with chapter officers only, add the three `TRANSITIONS_*_ENABLED` rows from
[§5.4](#54-transition-reports-keys) with value `off` (Django admin → Configs → Add).
Add the other four rows too if you want them editable; code defaults apply when they
are missing. **Never** re-run `dbseed`, `loaddata default_configs` or
`loaddata feature_flags` on production
([§4.1](#41-fixtures-not-loaded-by-dbseed-load-manually)).

**4. First run, before scheduling anything.**

```bash
python manage.py generate_transition_obligations --dry-run
python manage.py generate_transition_obligations
python manage.py send_transition_report_reminders --dry-run   # how many emails would go out
```

The first generate looks back 365 days, so it creates a `missed` obligation for every
tracked role whose term ended in the past year. The first reminder run then emails
each of those as past due, to the former officer, the chapter Regent, and the
region's RDs and region address. In testing, 4 obligations (2 ended terms, 2 current)
produced 4 emails. If the dry-run count is more than a handful, baseline the ended
terms first:

```python
# python manage.py shell
from django.utils import timezone
from thetatauCMT.transitions import services
from thetatauCMT.transitions.models import ReportObligation

today = timezone.now().date()
backlog = ReportObligation.objects.filter(term_end__lt=today, last_reminder_offset_sent__isnull=True)
print(backlog.count())
backlog.update(last_reminder_offset_sent=min(services.get_reminder_offsets_days()))
```

Re-run the dry-run: it should now count only current-term officers, who get one
catch-up reminder and then the normal ladder. In testing, later daily generate runs
did not undo the baseline. Use a later cutoff (for example
`term_end__lt=today - datetime.timedelta(days=30)`, with `import datetime`) if
recently ended terms should still get one catch-up email. Do not delete the backlog
rows instead: the daily generate recreates them (natural-key upsert) and they would be
unreminded again. Because the per-obligation emails are suppressed, consider a
one-time announcement to Regents and RDs; they will otherwise only find old vacancies
under "Vacant positions to close". `send_transition_handoff_notices` is harmless on
day one: it emails only when a predecessor report exists, so it just records current
role changes as handled.

**5. Schedule the three daily tasks** on the PythonAnywhere Tasks page (same
invocation style as the existing tasks), generate first and the other two a bit later:

```
python manage.py generate_transition_obligations
python manage.py send_transition_report_reminders
python manage.py send_transition_handoff_notices
```

No `--dry-run` or `--lookahead-days` in the live schedule.

**6. Smoke test.** As an admin open `/transitions/`, `/transitions/dashboard/rates/`
and `/transitions/trends/`. As a Regent check your chapter's rows under Search
reports. As an officer, press **Start report** on a position whose report is not
assigned yet (or **Compose** an open one), save a draft and upload an attachment (the
first write to GCS for this feature). Start report creates the real obligation, so use
an officer who is fine keeping it; it only sends reminders as the due date approaches.
Confirm `/features/` lists Transition Reports and Rollbar stays quiet. After the first
scheduled run, confirm a reminder in Mailjet.

**7. Rollback.** Code: `git checkout <previous sha>` and reload; the new tables are
harmless if left in place. Emails: disable the three scheduled tasks (there is no
feature flag for the whole feature). Database:
`python manage.py migrate transitions zero` only if no reports have been submitted,
otherwise restore the backup.

`buildwatson` is not needed on a first deploy: no reports exist yet and each report
indexes itself on save. If reports are ever imported, run
`python manage.py buildwatson transitions.TransitionReport`.

### 8.2 Upgrading into the Bigs and Littles release

First release of the `biglittle` app (spec: `docs/specs/big-little.md`). It adds two
migrations (`biglittle` 0001 and 0002, new tables only: the pairings, and uploaded rows
waiting for review), one Python package (`igraph==1.0.0`),
two static files (`js/biglittle.js`, `js/family_tree.js`), feature-catalog and
role-guide entries, and one optional `Config` key. No scheduled tasks, no emails, no new
environment variables.

Run the standard flow in [§8](#8-updating-an-existing-deploy). Notes:

1. `pip install -r requirements/production.txt` **is required** this time, for igraph.
   It installs from a prebuilt wheel (manylinux_2_28, needs glibc 2.28 or newer). If pip
   starts compiling it from source, stop and check the PythonAnywhere system image before
   migrating. Check: `python -c "import igraph; print(igraph.__version__)"`.
2. After `collectstatic`, confirm both scripts are in the manifest:
   `grep -oE '(biglittle|family_tree)\.[a-f0-9]{12}\.js' staticfiles/staticfiles.json`.
3. Optional: add `BIG_LITTLE_MANAGER_ROLES` in Django admin
   ([§5.2](#52-setting-keys-default_configsjson)) only if roles other than the New Member
   Educator should manage the chapter's records. The code default applies when it is
   missing. Never `loaddata default_configs` on production.
4. Smoke test. As a chapter officer: Members > Bigs & Littles shows the roster with
   Record and Upload buttons; record a Big, then remove it. Open Members > Family Tree
   (plotly.js loads from `cdn.plot.ly`, which the CSP already allows), find a member with
   the search box and try the zoom buttons. As a plain member
   of another chapter, the first chapter's tree redirects to your own. Upload a CSV with
   the names template (`little_full_name,big_full_name`) holding one misspelled name: the
   row lands on the "Review uploaded names" page, where saving the suggestion records it.
   Confirm `/features/` lists the new entries and Rollbar stays quiet.
5. Rollback: `git checkout <previous sha>` and reload; the new tables are harmless if left
   in place. `python manage.py migrate biglittle zero` drops every recorded pairing and
   every upload row waiting for review, so back up first.

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
11. **Transition Reports (October 2026 release)**: seeds run, scope flags decided,
    first-run baseline done, then the three daily tasks scheduled
    ([§8.1](#81-upgrading-into-the-transition-reports-release-october-2026)).

---

## 11. SSL certificates

**Nothing to renew by hand.** As of 2026-08-07 `cmt.thetatau.org` uses
PythonAnywhere's *Auto-renewed Let's Encrypt certificate* (Web page → **Security**
→ HTTPS certificate). PythonAnywhere issues, installs and renews it. There is no
scheduled task and no command to run. Docs:
<https://help.pythonanywhere.com/pages/HTTPSSetup>

`cmt.thetatau.info` resolves to Cloudflare, not PythonAnywhere, so its
certificate is Cloudflare's and auto-renews separately. The PythonAnywhere cert's
SAN covers `cmt.thetatau.org` only, which is correct.

Note `SECURE_HSTS_SECONDS` is 1 year with `SECURE_HSTS_PRELOAD` on
([config/settings/production.py](../config/settings/production.py)), so a lapsed
certificate is a hard outage for returning visitors, with no click-through. That
is the main reason not to go back to a hand-rolled renewal.

Check what is actually being served (works from any machine, no server access):

```bash
openssl s_client -connect cmt.thetatau.org:443 -servername cmt.thetatau.org </dev/null 2>/dev/null | openssl x509 -noout -subject -issuer -dates
```

### Retired: manual dehydrated renewal

The site previously ran a daily task doing `dehydrated --cron` plus
`pa_install_webapp_letsencrypt_ssl.py`. **Do not revive it.** It failed for
months with

```
bash: /home/<user>/.local/bin/pa_install_webapp_letsencrypt_ssl.py:
/usr/local/bin/python3.6: bad interpreter: No such file or directory
... return code was 126.
```

because the `pythonanywhere` helper package was installed with a Python that
PythonAnywhere later removed from the image. The failure was easy to miss:
dehydrated ran first and logged "Certificate will not expire ... Skipping renew!",
so the task *looked* healthy while the install step, the one that binds the cert
to the web app, never ran. Left alone it would have renewed the cert on disk and
still served an expired one.

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
# LMS_*, ED_*, EXECUTIVE_DIRECTOR, EVENTS_AUTO_APPROVE_NATIONAL_PUBLIC,
# GUARDIAN_EMAIL, GUARDIAN_PASSWORD, etc.

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
```

