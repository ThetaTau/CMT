"""Shared guard so demo/QA seed commands cannot run in production by accident.

Seed commands create demo/QA fixtures and must never run automatically against a
production database. This mirrors the inline guard already used by
``seed_awards_demo``: refuse to run unless ``settings.DEBUG`` is on or the
operator explicitly passes ``--force``.
"""

from django.conf import settings
from django.core.management.base import CommandError


def ensure_seeding_allowed(force=False):
    """Raise :class:`CommandError` in a production-like env unless ``force``."""
    if not settings.DEBUG and not force:
        raise CommandError(
            "Refusing to seed demo/QA data outside DEBUG without --force "
            "(this command must not run automatically in production)."
        )
