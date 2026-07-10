"""Celery task wrapper for the weekly contact sync.

Mirrors the pattern in :mod:`thetatauCMT.users.tasks` — the real work lives in
the ``weekly_contact_sync`` Django management command so PythonAnywhere-style
cron schedules can trigger it without a broker.
"""

from celery import shared_task
from django.core import management


@shared_task
def weekly_contact_sync() -> str:
    try:
        management.call_command("weekly_contact_sync", verbosity=0)
    except Exception as exc:  # noqa: BLE001 - Celery serialisation friendly
        return f"failure: {exc}"
    return "success"
