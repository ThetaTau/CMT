# thetatauCMT — Copilot instructions

## Runtime environment
- **Everything runs in docker containers.** Do NOT use the local virtualenv
  (e.g. `c:\workspace\.virtualenvs\cmt-prod2025`) for `python`, `manage.py`,
  `pytest`, `pip`, `django-admin`, or `check`.
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

## Stack
- Django 4.2.x, Python 3.13-slim, PostgreSQL 12, allauth 65.x, viewflow.

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
