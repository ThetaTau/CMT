# thetatauCMT — Copilot instructions

## Runtime environment (LOCAL DEVELOPMENT)
- **Local development runs in docker containers.** Do NOT use the local virtualenv
  (e.g. `c:\workspace\.virtualenvs\cmt-prod2025`) for `python`, `manage.py`,
  `pytest`, `pip`, `django-admin`, or `check`.
  This section is about local dev only. Production is NOT docker; see Deployment below.
- The Django service is the compose service `django`, container name
  `thetataucmt_local_django` (docker lowercases the project prefix).
- Run commands with `docker exec`:
  - Tests (full): `docker exec thetataucmt_local_django pytest --tb=no -q`
  - Tests (targeted): `docker exec thetataucmt_local_django pytest <path> -v --tb=short`
  - Django management: `docker exec thetataucmt_local_django python manage.py <cmd>`
  - Shell: `docker exec -it thetataucmt_local_django bash`
- Bring the stack up with `docker-compose -f docker-compose.local.yml up -d`
  (docker-compose works too). Never `pip install` on the host.
  - **Stack:** Django + PostgreSQL in Docker containers. Reuse existing app patterns. Use Django Viewflow for any approval workflow — follow the SAME patterns used in the recently built Volunteer Nomination flow (config-driven task assignment, Process/Flow classes, node types, templates).
- **Roles:** Member, Chapter Officer, RD (Regional Director), National Officer, Admin. Map all permissions to these existing roles. Reference positions from `core.models.NAT_OFFICERS` where relevant.
- **Working style:** Prefer configuration over hard-coded rules. Establish migrations/models FIRST and pause for confirmation, then services/logic, then views/templates, then tests by acceptance criterion. Gate every capability by role/permission.

## Deployment (PRODUCTION IS NOT DOCKER)
- Production is **PythonAnywhere + mod_wsgi** at `https://cmt.thetatau.org`,
  settings module `config.settings.production`. Runbook: [docs/deploy.md](../docs/deploy.md).
- `compose/production/`, `production.yml` and `docker-compose.production.yml` exist
  in the repo but are **NOT the live deployment path**. Never diagnose a production
  problem from them.
- Env vars come from the virtualenv `postactivate`; `workon thetatauCMT` is what
  exports `DJANGO_SETTINGS_MODULE=config.settings.production`.
- Static files use `CompressedManifestStaticFilesStorage` in production and plain
  `StaticFilesStorage` locally, and `manage.py` defaults to `config.settings.local`.
  Running `collectstatic` without the production settings updates the unhashed files
  but leaves `staticfiles.json` stale, so pages keep serving the old hashed asset
  under an `immutable` cache header. See docs/deploy.md §8.

## Stack
- Django 4.2.x, Python 3.13-slim, PostgreSQL 12, allauth 65.x, viewflow.

## Feature catalog (required for every user-facing change)
- Every new user-facing page or capability MUST be registered in the feature
  catalog: add an entry to
  `thetatauCMT/guides/fixtures/feature_registry.json` in the matching area.
  Reword or retire (`"is_active": false`) neighboring entries the change makes
  wrong. This is not optional cleanup; an unregistered page is invisible at
  `/features/`.
- Required keys: `key` (stable slug, never renamed), `name`,
  `short_description` (<=300 chars). Add `long_description`, `audience`
  (inherits the area when blank), `roles`, `task`, `url_kwargs`,
  `url_fragment`, `feature_flag` as they apply. Display order = list position.
- `url_name` must answer a GET. POST-only handlers give a 405; link the page
  that hosts the control and use `url_fragment` to scroll to it.
- Verify: `docker exec thetataucmt_local_django python manage.py
  load_feature_registry --dry-run`, then run `pytest thetatauCMT/guides`
  (`test_every_fixture_url_name_answers_get` guards the URL rule).
- Details and gotchas: `docs/specs/feature-registry.md`.

## Test suite
- Baseline: ~1065 passing, ~18 skipped, 0 failing.
- If a change should be verified, run the targeted pytest inside the container
  (see command above) — do not invoke pytest from the host venv.

## Project memory / lessons learned
- Detailed, dated engineering notes from past Copilot sessions live in
  [.github/copilot-memory/](copilot-memory/). Start with
  `copilot-memory/thetatauCMT-status.md` — it captures feature history, subtle
  bugs/fixes, test patterns, and repo-specific gotchas not obvious from the code.
  Consult it before implementing changes. Past per-session planning docs are under
  `copilot-memory/sessions/`.
