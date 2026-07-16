# thetatauCMT — Copilot instructions

## Runtime environment
- **Everything runs in Podman containers.** Do NOT use the local virtualenv
  (e.g. `c:\workspace\.virtualenvs\cmt-prod2025`) for `python`, `manage.py`,
  `pytest`, `pip`, `django-admin`, or `check`.
- The Django service is the compose service `django`, container name
  `thetataucmt_local_django` (Podman lowercases the project prefix).
- Run commands with `podman exec`:
  - Tests (full): `podman exec thetataucmt_local_django pytest --tb=no -q`
  - Tests (targeted): `podman exec thetataucmt_local_django pytest <path> -v --tb=short`
  - Django management: `podman exec thetataucmt_local_django python manage.py <cmd>`
  - Shell: `podman exec -it thetataucmt_local_django bash`
- Bring the stack up with `docker-compose -f docker-compose.local.yml up -d`
  (podman-compose works too). Never `pip install` on the host.

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
