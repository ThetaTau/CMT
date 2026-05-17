"""manage.py check and migration plan smoke tests (Phase 0.5.6).

Cheap canary for settings/model regressions:
- SystemCheckError from check() means a Django setting, installed app, or
  model definition has a configuration error.
- Unapplied migrations means a migration file was added without being applied
  to the test database (i.e., --reuse-db is stale or a migration is missing).
"""
import pytest
from io import StringIO

from django.core.management import call_command


@pytest.mark.django_db
def test_system_check_passes():
    """manage.py check exits clean — no ERROR or CRITICAL system-check issues."""
    out = StringIO()
    # Raises SystemCheckError if any ERROR/CRITICAL checks fail; the test
    # simply fails if that exception propagates.
    call_command("check", stdout=out, stderr=StringIO())
    assert "no issues" in out.getvalue(), (
        f"System check output did not confirm clean state:\n{out.getvalue()}"
    )


@pytest.mark.django_db
def test_no_unapplied_migrations():
    """migrate --plan reports no pending operations — schema matches codebase."""
    out = StringIO()
    call_command("migrate", "--plan", "--no-input", stdout=out, stderr=StringIO())
    plan_output = out.getvalue()
    assert "No planned migration operations" in plan_output, (
        f"Unapplied migrations detected:\n{plan_output}"
    )
