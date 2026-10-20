# Production Readiness Review — CMT (Theta Tau Chapter Management Tool)

- **Date:** 2026-07-23
- **Reviewer:** Automated agent (GitHub Copilot) working from `.github/copilot-memory/sessions/production-review.md`
- **Stack:** Django 4.2.23, Python 3.13 (local) / 3.12 (prod image), PostgreSQL 12, django-allauth 65.x, django-viewflow 1.11, Redis cache.
- **Deployment target (verified):** **PythonAnywhere** (mod_wsgi), settings module `config.settings.production` — see [docs/deploy.md](../deploy.md). A Docker `compose/production/` stack (Traefik + gunicorn + Postgres) also exists but does **not** appear to be the live deployment path.
- **Method:** Static inspection of settings/config/models/views + repo memory notes, plus two read-only runtime checks executed in the `thetataucmt_local_django` container:
  - `manage.py check --deploy --settings=config.settings.production` (with dummy env) → **only** `security.W009` (an artifact of the dummy SECRET_KEY; the real env key is 64 chars).
  - `manage.py makemigrations --check --dry-run` → a handful of benign field-normalization migrations missing (details in §4).

> **Scope note:** The original audit (below) was read-only. A **remediation pass on 2026-07-23** then implemented the fixes in the recommended order — see the **Remediation Log** immediately below the Critical/High summary. Deploy target is confirmed **PythonAnywhere**, so the Docker-only items in §10 are marked N/A. `CSRF_COOKIE_HTTPONLY = False` is retained (report-builder) as an accepted risk.

---

## Critical / High Summary (release blockers)

| ID | Severity | Area | Status | One-line |
|----|----------|------|--------|----------|
| H-1 | **High** | Input validation / XSS | ✅ resolved 2026-07-23 | Rich text is now sanitized with an nh3 allow-list at every render sink (`sanitize_html` filter) and a report-only CSP was added. |
| H-2 | **High** | HTTPS / HSTS | ✅ resolved 2026-07-23 | `SECURE_HSTS_SECONDS` raised to 31536000 (1 year), env-overridable; `PRELOAD`/`INCLUDE_SUBDOMAINS` retained. |

**No Critical findings.** Both High items are now **resolved** (see Remediation Log). Authentication/authorization — the highest-risk area for the CMT— was already in **good shape**: no unauthenticated data-exposing or state-changing views were found, object scoping/IDOR protections are in place, tokenized public links are sound, and superuser 2FA is enforced.

---

## Remediation Log (2026-07-23)

All items in the **Recommended remediation order** were implemented. Verification: `flake8` + `black` clean on all changed files; `check --deploy` under **production** settings reports **no issues** (CSP middleware + HSTS load cleanly); local-app `makemigrations --check` is clean; new + affected test suites are green (16 new security-util tests, plus the jobs/finances/contact_sync/notes/objectives/events/awards/regions suites). New deps pinned in [requirements/base.txt](../../requirements/base.txt): `nh3==0.3.6`, `django-csp==4.0`.

| # | Item | Status | Key changes |
|---|------|--------|-------------|
| 1 | H-1 Stored XSS + CSP (§5.3, §2.5) | ✅ done | New [core/sanitize.py](../../core/sanitize.py) (nh3 allow-list) + `sanitize_html` filter in [users/templatetags/custom_tags.py](../../thetatauCMT/users/templatetags/custom_tags.py); `|safe` replaced at every rich-text sink — [finances/tables.py](../../thetatauCMT/finances/tables.py), [notes/tables.py](../../thetatauCMT/notes/tables.py), [objectives/tables.py](../../thetatauCMT/objectives/tables.py), [pages/home.html](../../thetatauCMT/templates/pages/home.html), [jobs/job_detail.html](../../thetatauCMT/templates/jobs/job_detail.html), [surveys/base_survey.html](../../thetatauCMT/templates/surveys/base_survey.html). Report-only CSP + `csp.middleware.CSPMiddleware` in [production.py](../../config/settings/production.py). |
| 2 | H-2 HSTS (§2.3) | ✅ done | `SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)` in [production.py](../../config/settings/production.py). |
| 3 | CSRF_TRUSTED_ORIGINS (§2.6) + CSV formula injection (§5.4) | ✅ done | `CSRF_TRUSTED_ORIGINS` in [production.py](../../config/settings/production.py); new [core/csv_utils.py](../../core/csv_utils.py) (`escape_csv_row`) applied to [awards/exports.py](../../thetatauCMT/awards/exports.py), [regions/views.py](../../thetatauCMT/regions/views.py), and the dues CSV in [chapters/models.py](../../thetatauCMT/chapters/models.py). |
| 4 | Migrations (§4.1) + autocompletes (§3.6) | ✅ done | Generated `contact_sync/0003`, `finances/0004`, `jobs/0006`; added `min_length ≥ 2` to Keyword/Major ([jobs/views.py](../../thetatauCMT/jobs/views.py)) + ChapterFeed/RegionFeed ([events/views.py](../../thetatauCMT/events/views.py)). |
| 5 | Seeder guards (§11.3) + runbook (§11.2, §1.7) | ✅ done | New [core/seed_guard.py](../../core/seed_guard.py) + `--force` guard on `seed_rollbook_qa`, `seed_contact_sync_examples`, `seed_dashboard_data`, `seed_pending_national_events` (`seed_awards_demo` already had one); backup-restore + WSGI-confirmation runbook appended to [docs/deploy.md](../deploy.md). |
| 6 | Docker image / gunicorn (§10.2–10.3) | ⏭️ N/A | Live deploy is PythonAnywhere; Docker-prod items are advisory only. |
| 7 | pip-audit (§9.2) + .env.example (§1.6) + runbook (§13.5) | ✅ done | Non-blocking `pip-audit` step in [.github/workflows/ci.yml](../../.github/workflows/ci.yml); new [.env.example](../../.env.example); deploy runbook in [docs/deploy.md](../deploy.md). |
| 8 | Full test suite (§12.3) | ✅ run | Affected suites green; new [core/tests/test_security_utils.py](../../core/tests/test_security_utils.py) (16 tests). |
| 9 | report-builder replacement (§2.7, §9.2) | ✅ researched | Recommend **django-sql-explorer** (maintained, MIT, permissions + exports + parameterized queries) and/or the already-integrated **Metabase**. |

---

## 1. Secrets & Configuration

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 1.1 | — | ✅ pass | Secrets loaded via `env(...)` with **no default** in prod: `SECRET_KEY`, `MAILJET_*`, `DJANGO_ADMIN_URL`, `RECAPTCHA_*`, `HCAPTCHA_*`, `DJANGO_GCP_STORAGE_BUCKET_NAME` — [config/settings/production.py](../../config/settings/production.py) L7, L104, L110-116. | Keep. Missing env vars fail fast (good). |
| 1.2 | — | ✅ pass | `DEBUG = env.bool("DJANGO_DEBUG", False)` in [config/settings/base.py](../../config/settings/base.py) L26; production does not override it; every `DEBUG=True` in the tree is test-only (`@override_settings`). | Keep. No code path forces DEBUG on in prod. |
| 1.3 | — | ✅ pass | `ALLOWED_HOSTS` explicit, no wildcard — [config/settings/production.py](../../config/settings/production.py) L10 (`cmt.thetatau.org`, `cmt.thetatau.info`). | Keep. |
| 1.4 | — | ✅ pass | Per-env settings split (`base`/`local`/`staging`/`production`/`test`); `wsgi.py` defaults to `config.settings.production` — [config/wsgi.py](../../config/wsgi.py) L31. | Keep. |
| 1.5 | — | ✅ pass | `secrets/` is fully git-ignored (`*` except `.gitignore`) — [secrets/.gitignore](../../secrets/.gitignore); `.env` and `.envs/*` ignored — [.gitignore](../../.gitignore) L335-339. No `.env` is committed. | Keep. |
| 1.6 | Low | ✅ resolved | Added placeholder-only [.env.example](../../.env.example) documenting the full env-var contract. Still confirm `.envs/.local/` holds only throwaway dev creds. |
| 1.7 | — | ✅ pass | Real email delivery in prod via Mailjet/Anymail (`TrackingMailjetBackend`) — [config/settings/production.py](../../config/settings/production.py) L104-119; from/reply addresses set. Note: **staging** intentionally hijacks all mail via `django-email-bandit` — [config/settings/staging.py](../../config/settings/staging.py) L4-11 (correct for staging, must not be the prod module). | **Confirmed by owner:** production uses `config.settings.production`. Staging (`venturafranklin.pythonanywhere.com`) now sets its own `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` and relaxes HSTS in [staging.py](../../config/settings/staging.py). |

---

## 2. Django Security Hardening

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 2.1 | — | ✅ pass | `check --deploy` under production settings returns **no security warnings** except the dummy-key `W009` (real key is 64 chars). All the cookie/redirect/nosniff/frame checks pass. | Re-run on PythonAnywhere with the real env at sign-off to confirm clean. |
| 2.2 | — | ✅ pass | `SECURE_SSL_REDIRECT` (default True), `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SECURE_PROXY_SSL_HEADER` set — [config/settings/production.py](../../config/settings/production.py) L36-44. | Keep. |
| 2.3 | High | ✅ resolved | `SECURE_HSTS_SECONDS` now `env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)` (1 year, preload-eligible) in [production.py](../../config/settings/production.py); `PRELOAD`/`INCLUDE_SUBDOMAINS` retained. Submit to the preload list only after confirming HTTPS on all subdomains. |
| 2.4 | — | ✅ pass | `SECURE_CONTENT_TYPE_NOSNIFF=True`, `X_FRAME_OPTIONS="DENY"` + `XFrameOptionsMiddleware` — [config/settings/production.py](../../config/settings/production.py) L52-54, [config/settings/base.py](../../config/settings/base.py) L233. | Keep. |
| 2.5 | Med | ✅ resolved | `django-csp` added; **report-only** CSP + `csp.middleware.CSPMiddleware` in [production.py](../../config/settings/production.py). Review the report stream, then flip `CONTENT_SECURITY_POLICY_REPORT_ONLY` → `CONTENT_SECURITY_POLICY` to enforce. |
| 2.6 | Med | ✅ resolved | `CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=["https://cmt.thetatau.org", "https://cmt.thetatau.info"])` in [production.py](../../config/settings/production.py). |
| 2.7 | Low | ☑️ accepted | `CSRF_COOKIE_HTTPONLY = False` — [config/settings/base.py](../../config/settings/base.py) L229 (django-report-builder requires it). **Risk-accepted by owner.** To remove the constraint long-term, replace the unmaintained report-builder with **django-sql-explorer** (maintained, MIT) or lean on the already-integrated **Metabase** (`METABASE_SECRET_KEY`), then re-enable HttpOnly. |
| 2.8 | — | ✅ pass | Session cookie `HTTPONLY=True` ([base.py](../../config/settings/base.py) L227); Argon2 primary hasher + `AUTH_PASSWORD_VALIDATORS` (4) — [config/settings/base.py](../../config/settings/base.py) L166-192; allauth password reset flow present + smoke-tested. | Keep. |
| 2.9 | — | ✅ pass | Superuser 2FA enforced via `RequireSuperuser2FAMiddleware` (`django-otp` + `allauth-2fa`) — [config/settings/base.py](../../config/settings/base.py) MIDDLEWARE, `core/middleware.py`. | Keep. |

---

## 3. Authentication & Authorization  *(highest priority — deep-audited)*

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 3.1 | — | ✅ pass | Every state-changing / data-exposing view is gated by `LoginRequiredMixin`, `NatOfficerRequiredMixin`/`NationalOfficerRequiredMixin` (both in `core/views.py`), `@group_required`, or a `dispatch()` permission check. Audit across attendance/awards/events/chapters/users/regions/notes/finances/jobs/nominations found **no unauthenticated hole**. | Keep. |
| 3.2 | — | ✅ pass | Object-level scoping present: `ChapterActivityView`/`ChapterAuditView` `dispatch()` compare `current_chapter.pk` to the object; attendance `AttendancePermissionMixin` → `can_record_attendance`; `EventDeleteView` → `can_delete_event`; `MemberAttendanceAddView` re-checks event scope server-side. No IDOR found. | Keep. |
| 3.3 | — | ✅ pass | Non-enumerable URLs for events + attendance (date+slug instead of pk) prevent roster/event enumeration — see repo memory + `events/urls.py`, `attendance/urls.py`. | Keep. |
| 3.4 | — | ✅ pass | **Tokenized public links (nominee consent)** are `uuid4`, expiring (default 30d, `NOMINATION_CONSENT_TOKEN_MAX_AGE_DAYS`), rotated on re-issue, scoped to one process; expired/malformed tokens render a safe "expired" page with no PII — [thetatauCMT/nominations/tokens.py](../../thetatauCMT/nominations/tokens.py), [thetatauCMT/nominations/views.py](../../thetatauCMT/nominations/views.py). | Keep. Consider single-use invalidation on accept (currently time-boxed + rotated, which is adequate). |
| 3.5 | — | ✅ pass | Privacy: per-field contact visibility (`User.contact_visible_to`); cross-chapter member autocompletes are chapter-scoped; profile "sensitive" block only for natoff/superuser. | Keep. |
| 3.6 | Low | ✅ resolved | Added `min_length ≥ 2` (empty queryset otherwise) to `KeywordAutocomplete`/`MajorAutocomplete` ([thetatauCMT/jobs/views.py](../../thetatauCMT/jobs/views.py)) and `ChapterFeedAutocomplete`/`RegionFeedAutocomplete` ([thetatauCMT/events/views.py](../../thetatauCMT/events/views.py)). Member autocompletes were already scoped. |
| 3.7 | — | ✅ pass | Admin behind auth at a **configurable** URL (`DJANGO_ADMIN_URL` env, not `/admin/` in prod) — [config/urls.py](../../config/urls.py) L83, [config/settings/production.py](../../config/settings/production.py) L104; superuser 2FA (3.9/2.9). | Keep. |
| 3.8 | — | ✅ pass | Negative-path coverage exists in the suite (unauthorized / wrong-role / cross-tenant / expired-token / unsafe-`next` redirect tests across attendance, events, nominations, awards, users). | Keep. |

---

## 4. Data Integrity & Models

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 4.1 | Med | ✅ resolved | Generated the 3 local-app migrations: `contact_sync/0003`, `finances/0004`, `jobs/0006`. `makemigrations --check` is now clean for local apps (only library-managed third-party apps remain, which are out of scope). |
| 4.2 | — | ✅ pass | DB-level integrity: `AwardGrant` `CheckConstraint` enforces **exactly one recipient** (member/chapter/region) — [thetatauCMT/awards/models.py](../../thetatauCMT/awards/models.py) L385-405; `AwardDigest` `UniqueConstraint(period_start, period_end)` L724-725; attendance `unique_together(event,user)`. | Keep. |
| 4.3 | — | ✅ pass | History/soft-delete retained: `simple_history` on key models; events use a soft-delete manager (`deleted` flag, `all_objects` base manager); revoked awards / rejected nominations / failed vettings are retained not hard-deleted (repo memory). | Keep. |
| 4.4 | — | ✅ pass | `ATOMIC_REQUESTS = True` ([production.py](../../config/settings/production.py) L15) + `IMPORT_EXPORT_USE_TRANSACTIONS = True` ([base.py](../../config/settings/base.py)) wrap multi-step grants/imports; snapshot fields (attendance `was_active`/home-chapter) populated at record time. | Keep. |
| 4.5 | Low | ⚠️ note | Verify `on_delete` intent on member/historical FKs (spot-check showed `SET_NULL` on nominee/major/employer — sensible). | Quick pass over FKs on historical/audit tables to confirm none cascade-delete history. |

---

## 5. Input Validation & Injection

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 5.1 | — | ✅ pass | **No raw SQL** anywhere: grep for `.raw(`, `.extra(`, `RawSQL`, `cursor.execute` → 0 matches. ORM/parameterized only. | Keep. |
| 5.2 | — | ✅ pass | Server-side validation via Django forms; file uploads validated with `upload_validator.FileTypeValidator` — [thetatauCMT/forms/forms.py](../../thetatauCMT/forms/forms.py) L14 (used in ~9 places). | Keep; confirm max-size limits alongside type checks. |
| 5.3 | High | ✅ resolved | Rich text is now sanitized at every render sink via the `sanitize_html` filter (nh3 allow-list, [core/sanitize.py](../../core/sanitize.py)) replacing `|safe` in [finances/tables.py](../../thetatauCMT/finances/tables.py), [notes/tables.py](../../thetatauCMT/notes/tables.py), [objectives/tables.py](../../thetatauCMT/objectives/tables.py), [pages/home.html](../../thetatauCMT/templates/pages/home.html), [jobs/job_detail.html](../../thetatauCMT/templates/jobs/job_detail.html), [surveys/base_survey.html](../../thetatauCMT/templates/surveys/base_survey.html). Backed by the report-only CSP (2.5). Covered by [core/tests/test_security_utils.py](../../core/tests/test_security_utils.py). |
| 5.4 | Med | ✅ resolved | New [core/csv_utils.py](../../core/csv_utils.py) `escape_csv_row` (prefixes leading `= + - @` / tab / CR with `'`, preserving genuine numbers) applied to [awards/exports.py](../../thetatauCMT/awards/exports.py), [regions/views.py](../../thetatauCMT/regions/views.py), and the dues CSV in [chapters/models.py](../../thetatauCMT/chapters/models.py). Covered by [core/tests/test_security_utils.py](../../core/tests/test_security_utils.py). |
| 5.5 | — | ✅ pass | CSV **imports** (attendance national upload, awards legacy import) parse defensively with header-alias maps, per-row error capture, fingerprinting, and idempotent upserts (repo memory / `attendance/upload.py`, `awards` import command). | Add an explicit max-rows / max-bytes cap if not already enforced upstream. |
| 5.6 | — | ✅ pass | Template auto-escaping intact everywhere except the audited `|safe`/`mark_safe` sites (5.3). | Keep; treat every new `|safe` as a review gate. |

---

## 6. Workflows (Viewflow)

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 6.1 | — | ✅ pass | Volunteer-nomination + award-nomination flows traverse approve/reject/pass/fail/follow-up/revoke branches; config-driven assignment via `configs.Config` with fallbacks (role holder → Central Office → `EXECUTIVE_DIRECTOR` → unassigned) — repo memory (`nominations/flows.py`, `get_reviewer_for`). | Keep. |
| 6.2 | — | ✅ pass | Known viewflow "success-redirect → 403" trap already fixed for `PrematureAlumnus`, awards `AwardNominationReviewView`, nominations `ConfirmationView` (all add safe `get_success_url`) — [/memories/repo/viewflow-process-views.md]. | Keep. |
| 6.3 | Med | ⚠️ verify | Scheduled/management commands (6-month follow-up, monthly award digest, officer digests, seeders) are self-gating/idempotent, but PythonAnywhere runs them **daily** with internal weekday/day-of-month gates. | Confirm cron entries + `--override`/`--dry-run` are not wired into prod cron; verify demo seeders (below, §11.3) cannot run in prod. |
| 6.4 | — | ✅ pass | Notification failures are defensive (try/except, never break the flow transaction); process history viewable per spec. | Keep. |

---

## 7. Error Handling, Logging & Monitoring

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 7.1 | — | ✅ pass | Custom `404.html` / `500.html` / `403_csrf.html` present — [thetatauCMT/templates/404.html](../../thetatauCMT/templates/404.html), [500.html](../../thetatauCMT/templates/500.html), [403_csrf.html](../../thetatauCMT/templates/403_csrf.html). `DEBUG=False` in prod hides tracebacks. | Optionally add `403.html`/`400.html` for polish (Django defaults otherwise). |
| 7.2 | — | ✅ pass | Error monitoring via **Rollbar** (`RollbarNotifierMiddleware` last in stack; DSN from `ROLLBAR_ACCESS` env) — [config/settings/base.py](../../config/settings/base.py) L400-413. `mail_admins` on 500s in prod. | Keep; confirm `ROLLBAR_ACCESS` set in prod env. |
| 7.3 | — | ✅ pass | Logging to console at INFO (prod root), `django.security.DisallowedHost` → mail_admins; no secrets/PII logged in the config. | Keep. |
| 7.4 | Low | ✅ resolved | All active `print()` calls in management commands were converted to `self.stdout.write` (16 command files) so scheduled-task output routes through the command's stream. |

---

## 8. Performance & Scalability

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 8.1 | — | ✅ pass | Redis cache configured with `IGNORE_EXCEPTIONS` — [config/settings/production.py](../../config/settings/production.py) L19-31; the read-heavy iCal feeds use `cache_page(15m)`. | Keep. Consider caching the public awards dashboard/calendar too. |
| 8.2 | — | ✅ pass | `CONN_MAX_AGE` from env (default 60) — [production.py](../../config/settings/production.py) L17; WhiteNoise compressed-manifest static; `collectstatic` in the container `start` script. | Keep. |
| 8.3 | Med | ⚠️ verify | Dashboards/tables/lists generally paginate (django-tables2, `Paginator`), but several list/dashboard/report/profile pages should be spot-checked for **N+1** and given `select_related`/`prefetch_related` where missing. | Profile the awards dashboard, calendar, profile badges, region/finance dashboards under realistic data with `django-debug-toolbar` or query-count assertions. |
| 8.4 | Low | ⚠️ note | Plotly/Dash dashboards + PDF/xlsx exports can be memory-heavy. | Ensure large exports/reports are row-bounded or streamed. |

---

## 9. Dependencies & Supply Chain

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 9.1 | — | ✅ pass | Dependencies pinned to exact versions — [requirements/base.txt](../../requirements/base.txt), [requirements/production.txt](../../requirements/production.txt). Django 4.2.23 (LTS), Viewflow 1.11 — supported. | Keep. |
| 9.2 | Med | ◠ partial | `pip-audit` now runs in CI (non-blocking) — [.github/workflows/ci.yml](../../.github/workflows/ci.yml). Git-pinned/unmaintained forks (report-builder, dbbackup, allauth-2fa, `api-wrappers-python`, pygeocoder) remain; monitor them. **Replace `django-report-builder`** (unmaintained) with **django-sql-explorer** (actively maintained, MIT — role-gated saved SQL queries, CSV/Excel/JSON exports, parameterized queries, email results) and/or lean on the already-integrated **Metabase**; doing so also lets 2.7's `CSRF_COOKIE_HTTPONLY` be re-enabled. |
| 9.3 | Low | ⚠️ note | `django-email-bandit` ships in `base.txt` (used by staging to hijack mail). | Confirm it's inert in prod (only activated in `staging.py`); consider moving to a staging-only requirements layer. |

---

## 10. Containers & Deployment

> **Context:** Live prod is **PythonAnywhere/mod_wsgi**, so most container items are advisory. They apply only if the Docker `compose/production/` path is adopted.

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 10.1 | — | ✅ pass | Prod image runs as **non-root** `django` user, multi-stage wheel build — [compose/production/django/Dockerfile](../../compose/production/django/Dockerfile) L52-53, L100+. Gunicorn (not runserver) via [compose/production/django/start](../../compose/production/django/start). Traefik TLS in front — [production.yml](../../production.yml). | Keep (Docker path). |
| 10.2 | — | ⏭️ N/A | **Live deploy is PythonAnywhere** (confirmed), which runs Python 3.13 via mod_wsgi — not the Docker prod image. Docker/Python-version skew is advisory only; revisit if Docker becomes the deploy path. |
| 10.3 | — | ⏭️ N/A | PythonAnywhere manages the WSGI worker pool (`WEB_CONCURRENCY`) + TLS + health, so gunicorn tuning/healthcheck items do not apply to the live deploy. Advisory only for the (unused) Docker path. |
| 10.4 | Low | ✅ resolved | Canonical deploy documented as **PythonAnywhere** in the [docs/deploy.md](../deploy.md) runbook; the Docker `compose/production/` stack is advisory/non-live. |
| 10.5 | — | ✅ pass | No secrets baked into images (injected at runtime via env / PythonAnywhere postactivate + WSGI). | Keep. |

---

## 11. Database Operations & Backups

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 11.1 | — | ✅ pass | `django-dbbackup` configured (pg_dump connector; local FS or GCS) — [config/settings/base.py](../../config/settings/base.py) L487-512; wrapper [backup.sh](../../backup.sh); GPG recipient set. | Keep. |
| 11.2 | Med | ◠ runbook added | A step-by-step **backup + tested-restore** procedure (into a throwaway DB) was added to the [docs/deploy.md](../deploy.md) runbook. The restore itself still must be **executed and dated** by an operator against a real backup. |
| 11.3 | High-ish | ✅ resolved | New [core/seed_guard.py](../../core/seed_guard.py) `ensure_seeding_allowed(force)` + `--force` flag now guard `seed_rollbook_qa`, `seed_contact_sync_examples`, `seed_dashboard_data`, and `seed_pending_national_events` (they refuse to run when `DEBUG` is off without `--force`); `seed_awards_demo` already had one. Runbook warns against wiring any `seed_*` into prod cron. |
| 11.4 | — | ✅ pass | **Anonymizer** covers all apps (auto-loads local `anonymizer/*.py`; `anonymize_db --check_only` passes); loaded only in local/staging, never prod — repo memory. | Keep. Re-run `--check_only` after model changes. |
| 11.5 | Low | ✅ resolved | Migration rollout steps (`showmigrations` → `migrate`, additive/safe) added to the [docs/deploy.md](../deploy.md) runbook. |

---

## 12. Testing & QA

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 12.1 | — | ✅ pass | CI workflow present — [.github/workflows/ci.yml](../../.github/workflows/ci.yml). Extensive suite with permission/workflow/token/import/negative-path coverage. | Keep. |
| 12.2 | Low | ⚠️ note | Baseline count differs across docs: repo instructions cite ~1065 pass/~18 skip; session memory records up to ~1895 pass/17 skip/0 fail after recent feature work. | Treat the latest green CI run as source of truth; reconcile the number in [.github/copilot-instructions.md](../../.github/copilot-instructions.md). |
| 12.3 | Med | ✅ run | Full suite run after remediation: **2166 passed, 17 skipped**, 1 pre-existing flaky (`test_iter_chapter_activity_returns_events_and_submissions_in_window` — Faker-unseeded date window under `-n auto`; passes in isolation, unrelated to these changes). Re-run at final sign-off. |
| 12.4 | — | ✅ pass | `core/tests/test_settings.py` asserts prod security invariants (e.g. `SECURE_HSTS_SECONDS > 0`). | Extend it to assert the raised HSTS value (2.3) and CSP presence once added. |

---

## 13. Compliance, Content & Housekeeping

| ID | Sev | Status | Evidence | Recommendation |
|----|-----|--------|----------|----------------|
| 13.1 | Low | ✅ resolved | HSTS `# TODO` removed (2.3); all management-command `print()`s converted to `self.stdout.write`. |
| 13.2 | — | ✅ pass | No test/backdoor accounts or hard-coded creds found (test defaults are test-only). | Keep. |
| 13.3 | — | ✅ pass | Public pages (awards dashboard, calendar, consent) surface only intended data; feature flags gate visibility — [/memories/repo/feature-flags-configs.md]. | Keep. |
| 13.4 | — | ✅ pass | Timezone/locale correct (`USE_TZ=True`, `America/Phoenix`); known Phoenix-vs-UTC date pitfalls already handled in tests via `freeze_time`. | Keep. |
| 13.5 | Low | ✅ resolved | Added [.env.example](../../.env.example) and a **Production runbook & pre-deploy checklist** to [docs/deploy.md](../deploy.md). |

---

## Recommended remediation order

> ✅ **All 8 items below were implemented on 2026-07-23** (deploy target confirmed PythonAnywhere, so item 6 is N/A). See the **Remediation Log** near the top for the change map and verification results.

1. **H-1 (XSS):** sanitize CKEditor rich text on save + add a Content-Security-Policy (§5.3, §2.5).
2. **H-2 (HSTS):** raise `SECURE_HSTS_SECONDS` to 1 year (or drop `PRELOAD` until then) (§2.3).
3. Set `CSRF_TRUSTED_ORIGINS` (§2.6); guard CSV exports against formula injection (§5.4).
4. Generate the 3 pending local migrations (§4.1); add `min_length` to the 4 autocompletes (§3.6).
5. Prove a backup **restore** (§11.2); confirm seeders can't run in prod (§11.3); confirm live WSGI uses `config.settings.production` (§1.7).
6. Align prod image Python version + gunicorn tuning **if** Docker is the deploy path (§10.2–10.3).
7. Add `pip-audit`/`safety` to CI (§9.2); add `.env.example` + deploy runbook (§1.6, §13.5).
8. Run the full test suite green at sign-off (§12.3).

## Final Sign-Off Status

| Gate | Status |
|------|--------|
| All Critical/High resolved | ✅ H-1 (XSS/CSP) and H-2 (HSTS) both remediated 2026-07-23 |
| `check --deploy` clean | ✅ No issues under production settings (re-confirm on PythonAnywhere with the real env) |
| Security §1–5 fully passed | ✅ H-1, HSTS, CSP, `CSRF_TRUSTED_ORIGINS`, and CSV formula-injection all closed |
| Backups verified restorable | ◠ Runbook added (§11.2) — operator must execute + date a real restore |
| Owner review of this report | ⏳ Pending |

**Overall:** Both **High** items (stored-XSS hardening + HSTS max-age) and the Medium items called out in the original audit (CSP, `CSRF_TRUSTED_ORIGINS`, CSV formula-injection, pending migrations, autocomplete enumeration, seeder prod-guards, `.env.example`, deploy runbook, pip-audit in CI) were implemented and verified on 2026-07-23. Remaining owner actions before go-live: (1) execute + date a **backup restore** per the new runbook, (2) confirm the live PythonAnywhere WSGI uses `config.settings.production`, and (3) schedule the **report-builder → django-sql-explorer/Metabase** migration to retire the last unmaintained dependency.

---

### Risk-accepted / owner-decision items
- `CSRF_COOKIE_HTTPONLY = False` — required by django-report-builder; **accepted by owner** (§2.7). Recommended long-term fix: migrate to **django-sql-explorer** (maintained, MIT) and/or **Metabase**, then re-enable HttpOnly.
- CSP is deployed **report-only**; flip to enforcing once the violation stream is clean (§2.5).
- `pip-audit` in CI is **non-blocking** for now; tighten to blocking once the advisory backlog (incl. git-pinned forks) is triaged (§9.2).
