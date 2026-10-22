# Production Readiness Review — Agent Checklist

> **Purpose:** A pre-production audit for the CMT application (Django + PostgreSQL, Podman containers, Viewflow workflows).
> **How to use (Claude/Copilot agent):** Work through each section in order. For every item: (1) inspect the relevant code/config, (2) report status as ✅ pass / ⚠️ risk / ❌ fail with file references, (3) propose a fix, and (4) pause for confirmation before applying changes that alter behavior, data, or security posture. Do NOT weaken security controls to make tests pass. Never commit secrets. Summarize findings per section before moving on.

---

## 0. How to Report
For each finding produce:
- **ID / Area**
- **Severity:** Critical / High / Medium / Low
- **Status:** pass / risk / fail
- **Evidence:** file path + line reference
- **Recommendation / fix**
- Group a **Critical/High summary** at the top of the final report. Critical and High items block release.

---

## 1. Secrets & Configuration
- [ ] **No secrets in the repo:** scan for API keys, passwords, `SECRET_KEY`, DB creds, email/SMTP creds, tokens (including in migrations, fixtures, tests, and commit history if feasible).
- [ ] `SECRET_KEY`, DB credentials, and all secrets are loaded from **environment variables / secret store**, not hard-coded.
- [ ] `DEBUG = False` in production settings; confirm no code path forces it on.
- [ ] `ALLOWED_HOSTS` is set explicitly (no wildcard `*` in prod).
- [ ] Separate settings for dev/prod; prod settings verified as the ones used by the container.
- [ ] `.env`/secret files are in `.gitignore`; provide a committed `.env.example` with placeholders only.
- [ ] Email backend configured for real delivery in prod (not console backend); "from" addresses and reply-to are correct.

## 2. Django Security Hardening
- [ ] Run `python manage.py check --deploy` and resolve all warnings.
- [ ] HTTPS enforced: `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` all `True`.
- [ ] `SECURE_HSTS_SECONDS` set (with `INCLUDE_SUBDOMAINS`/`PRELOAD` as appropriate).
- [ ] `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS` (clickjacking), and a **Content Security Policy** configured.
- [ ] `CSRF_TRUSTED_ORIGINS` set for the production domain(s).
- [ ] Session settings: reasonable expiry, `SESSION_COOKIE_HTTPONLY`, secure cookies, session invalidation on logout.
- [ ] CSRF protection active on all state-changing views/forms (including HTMX/AJAX/Viewflow actions).
- [ ] Password validators enabled; password reset flow tested.

## 3. Authentication & Authorization (highest priority for this app)
- [ ] **Every view/endpoint enforces auth + role permission** — no view relies on "hidden" UI alone. Audit views across attendance, volunteer, and awards apps.
- [ ] Role gating is correct and consistent: Member, Chapter Officer, RD, National Officer, Admin. Verify each capability maps to the intended role per the feature specs.
- [ ] **Object-level scoping**: chapter officers can only act within their chapter; RDs within their region; verify no IDOR (changing an ID in the URL/body to access another chapter's/member's data).
- [ ] Viewflow **task assignment/permissions**: only the configured assignee/role can complete each node; nodes cannot be skipped or completed out of order.
- [ ] **Tokenized public links** (volunteer nominee consent, any award links): tokens are single-use, expiring, unguessable, scoped to one process; expired/used tokens rejected gracefully; no sensitive data leaked on the public page.
- [ ] **Privacy constraints upheld**: cross-chapter member autocomplete never exposes a full roster; awards visibility matches "all public" intent but no non-public/PII fields leak.
- [ ] Admin site: restricted to Admin role, behind auth, ideally not at the default `/admin/` path or otherwise protected.
- [ ] Test negative cases: unauthenticated access, wrong-role access, and cross-tenant access all return 403/404, not data.

## 4. Data Integrity & Models
- [ ] Migrations are complete and consistent: `makemigrations --check --dry-run` shows no missing migrations; no conflicting/duplicate migrations.
- [ ] Constraints enforced at the DB level where they matter (e.g., AwardGrant "exactly one recipient", unique winner-per-cycle where single_winner, attendance uniqueness per member/event).
- [ ] Sensible `on_delete` behavior on all FKs (no accidental cascade deletes of historical records).
- [ ] **Soft-delete/retain history** honored: revoked awards, rejected nominations, and failed vettings are retained, not hard-deleted.
- [ ] Indexes on frequently filtered/joined fields (dashboards, reports, calendars, award lookups).
- [ ] Snapshot/audit fields populated correctly (attendance active-member snapshot; grant/audit trails; Viewflow process history).
- [ ] No orphaned records possible from partial workflow failures (wrap multi-step grants/imports in transactions).

## 5. Input Validation & Injection
- [ ] All user input validated server-side via Django forms/serializers (not just client-side).
- [ ] No raw SQL with string interpolation; parameterized queries only.
- [ ] **File uploads** (certificates, appointment/denial letters, imports): validate type/extension/size, store safely (no user-controlled paths), never serve uploads as executable, scan/limit as feasible.
- [ ] **CSV/bulk imports** (attendance national upload, awards legacy import): sanitize inputs, guard against CSV formula injection, enforce size/row limits, handle malformed rows gracefully.
- [ ] Autocomplete/search endpoints: enforce min query length, result caps, and scope filters (no enumeration).
- [ ] Template output auto-escaping intact; audit any `|safe`, `mark_safe`, or `{% autoescape off %}` usages.

## 6. Workflows (Viewflow)
- [ ] All flows (volunteer nomination, award nomination) traverse every branch correctly: approve/reject, pass/fail, follow-up, revoke/deny paths.
- [ ] Config-driven assignments resolve to valid users; handle the case where a configured assignee is missing/inactive.
- [ ] Scheduled/management commands (6-month follow-up, monthly award digest, seed) are idempotent, safe to re-run, and guarded against prod misuse.
- [ ] Notifications fire at the correct steps and don't duplicate; failures don't break the workflow transaction.
- [ ] Process history/audit is complete and viewable per spec.

## 7. Error Handling, Logging & Monitoring
- [ ] Custom 400/403/404/500 pages; no stack traces or debug info shown to users in prod.
- [ ] Centralized logging configured; logs do NOT contain secrets, tokens, or PII.
- [ ] Error monitoring (e.g., Sentry) or equivalent wired up with prod DSN from env.
- [ ] Unhandled-exception paths reviewed; background/command failures are logged and alertable.
- [ ] Log level appropriate for prod (no DEBUG-level noise).

## 8. Performance & Scalability
- [ ] Audit for **N+1 queries** on high-traffic/list pages: dashboards, calendar, awards dashboard, profile badges/inline name icons, reports. Use `select_related`/`prefetch_related`.
- [ ] Pagination on all large lists/tables/exports.
- [ ] Expensive reports/exports are bounded (row limits, streaming, or async) so they can't exhaust memory.
- [ ] Static files collected and served via `collectstatic` + WhiteNoise/CDN/reverse proxy; media served correctly.
- [ ] DB connection settings (pooling/`CONN_MAX_AGE`) suitable for the deployment.
- [ ] Caching used where sensible for read-heavy public pages (awards dashboard, calendar).

## 9. Dependencies & Supply Chain
- [ ] Dependencies pinned (lockfile/`requirements.txt` with versions).
- [ ] Vulnerability scan run (`pip-audit`/`safety`); resolve or document high/critical CVEs.
- [ ] Remove unused/dev-only packages from the prod image.
- [ ] Django and Viewflow on supported, patched versions.

## 10. Containers & Deployment (Docker)
- [ ] Production image does **not** run as root; uses a non-root user.
- [ ] No secrets baked into the image; injected at runtime.
- [ ] Multi-stage/lean image; no dev tooling, `.env`, or source-control metadata shipped.
- [ ] Healthcheck endpoint/readiness probe defined.
- [ ] Gunicorn/uwsgi (not `runserver`) as the app server; sensible worker/timeout config.
- [ ] Reverse proxy (TLS termination, security headers) in front; ports minimally exposed.
- [ ] Container restart policy and resource limits set.

## 11. Database Operations & Backups
- [ ] Automated PostgreSQL backups configured and **restore tested**.
- [ ] Migration rollout plan for prod (zero/low-downtime; reversible where possible).
- [ ] No demo/seed data in production; `seed_awards_demo` (and any seeder) guarded against prod execution.
- [ ] PII handling/retention reviewed for member data, letters, and uploads.
- [ ] Anonymizer is set up for all apps appropriately depending on the model and the data for that field.

## 12. Testing & QA
- [ ] Test suite passes; CI green.
- [ ] Coverage on critical paths: permissions/role gating, workflow transitions, eligibility rules, quorum/attendance snapshots, award grant/revoke, imports/matching.
- [ ] Negative/security tests exist (unauthorized access, cross-tenant, expired tokens, invalid imports).
- [ ] Manual QA walkthrough completed per feature (use the seed data) with sign-off.

## 13. Compliance, Content & Housekeeping
- [ ] No leftover `print()`/debug statements, `TODO`/`FIXME` blocking issues, or commented-out dead code in critical paths.
- [ ] No test/backdoor accounts or hard-coded credentials.
- [ ] Robots/SEO and privacy expectations correct for public pages (awards dashboard, public calendar) — only intended data is public.
- [ ] Timezone/locale handling correct (event dates, cycles, effective dates, backdated awards).
- [ ] README/deployment docs and runbook updated; env var list documented.

---

## Final Sign-Off
- [ ] All **Critical** and **High** findings resolved (or explicitly risk-accepted by the owner with rationale).
- [ ] `manage.py check --deploy` clean.
- [ ] Security section (1–5) fully passed.
- [ ] Backups verified restorable.
- [ ] Owner review of the agent's final report completed.

**Agent deliverable:** a single report at `docs/reviews/production-readiness-<date>.md` containing the per-section findings table, the Critical/High summary, applied fixes (with PR/commit links), and any risk-accepted items awaiting owner decision.
