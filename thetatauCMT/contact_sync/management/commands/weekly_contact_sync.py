"""Run the weekly auto-sync for every token that has enrolled scopes.

PythonAnywhere only offers *daily* scheduled tasks, so (like
``job_search_notify`` / ``region_officer_reminder_digest``) this command
self-gates to a single weekday (Thursday by default). Schedule it DAILY and
it only actually pushes on ``--weekday``.

``--override`` pushes right now regardless of the weekday gate. ``--dry-run``
prints what would happen without pushing anything, and also bypasses the
weekday gate so it can be tested on any day.

Usage::

    podman exec thetataucmt_local_django python manage.py weekly_contact_sync
    podman exec thetataucmt_local_django python manage.py weekly_contact_sync --user someone@example.com
    podman exec thetataucmt_local_django python manage.py weekly_contact_sync --dry-run
"""

from __future__ import annotations

import datetime

from django.core.management.base import BaseCommand

from thetatauCMT.contact_sync.models import UserContactSyncToken
from thetatauCMT.contact_sync.officers import collect_contacts_for_scope
from thetatauCMT.contact_sync.providers import get_provider, provider_is_configured
from thetatauCMT.contact_sync.providers.base import ProviderAuthError, ProviderNotConfigured

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Command(BaseCommand):
    help = "Push contact-sync updates for every token that has auto_sync_scopes set."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--user",
            help="Only sync tokens belonging to this user (by email or username).",
        )
        parser.add_argument(
            "--provider",
            help="Only sync tokens for a specific provider ('google' or 'microsoft').",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would happen without actually pushing (also bypasses the weekday gate).",
        )
        parser.add_argument(
            "--weekday",
            type=int,
            default=3,
            help="Weekday this actually pushes on when run daily (0=Monday ... 6=Sunday). Default Thursday.",
        )
        parser.add_argument(
            "--override",
            action="store_true",
            help="Push now regardless of the weekday gate.",
        )

    def handle(self, *args, **options) -> None:  # noqa: ANN401
        dry_run = options.get("dry_run", False)
        weekday = options.get("weekday", 3)
        override = options.get("override", False)

        # PythonAnywhere runs this daily; only actually push on the configured
        # weekday so auto-synced contacts update once a week. --override /
        # --dry-run bypass the gate.
        today_weekday = datetime.date.today().weekday()
        if today_weekday != weekday and not (override or dry_run):
            self.stdout.write(
                f"Not the scheduled day (today is {WEEKDAY_NAMES[today_weekday]}, "
                f"sync runs on {WEEKDAY_NAMES[weekday]}); skipping."
            )
            return

        qs = (
            UserContactSyncToken.objects.exclude(auto_sync_scopes__len=0)
            .select_related("user")
            .order_by("provider", "user_id")
        )
        if options.get("user"):
            qs = qs.filter(user__email__iexact=options["user"]) | qs.filter(user__username__iexact=options["user"])
        if options.get("provider"):
            qs = qs.filter(provider=options["provider"])

        total_tokens = qs.count()
        if total_tokens == 0:
            self.stdout.write(self.style.NOTICE("No tokens with auto_sync_scopes; nothing to do."))
            return
        self.stdout.write(self.style.NOTICE(f"Processing {total_tokens} auto-sync token(s)..."))

        total_pushed = 0
        total_errors = 0
        for token in qs:
            if not provider_is_configured(token.provider):
                self.stdout.write(
                    self.style.WARNING(f"  [skip] {token.user}: provider {token.provider!r} is not configured.")
                )
                continue
            provider = get_provider(token.provider)
            for scope in list(token.auto_sync_scopes or []):
                pushed, errored = self._sync_one(
                    provider=provider,
                    token=token,
                    scope=scope,
                    dry_run=dry_run,
                )
                total_pushed += pushed
                total_errors += errored

        self.stdout.write(
            self.style.SUCCESS(f"Done. Pushed contacts across {total_pushed} scope-run(s); {total_errors} error(s).")
        )

    # ------------------------------------------------------------------ helpers
    def _sync_one(self, *, provider, token: UserContactSyncToken, scope: str, dry_run: bool) -> tuple[int, int]:
        contacts, scope_display = collect_contacts_for_scope(scope)
        if not contacts:
            self.stdout.write(f"  [skip] {token.user} / {token.provider} / {scope}: 0 contacts.")
            return 0, 0
        if dry_run:
            self.stdout.write(
                f"  [dry] {token.user} / {token.provider} / {scope}: would push "
                f"{len(contacts)} contact(s) ({scope_display})."
            )
            return 1, 0
        try:
            provider.ensure_valid(token)
        except (ProviderAuthError, ProviderNotConfigured) as exc:
            token.record_sync_error(f"[weekly] refresh failed: {exc}")
            self.stdout.write(self.style.ERROR(f"  [error] {token.user} / {token.provider}: refresh failed: {exc}"))
            return 0, 1
        try:
            result = provider.push_contacts(token, contacts)
        except (ProviderAuthError, ProviderNotConfigured) as exc:
            token.record_sync_error(f"[weekly] push failed: {exc}")
            self.stdout.write(
                self.style.ERROR(f"  [error] {token.user} / {token.provider} / {scope}: push failed: {exc}")
            )
            return 0, 1
        token.record_sync_success(result.created + result.updated)
        self.stdout.write(
            self.style.SUCCESS(
                f"  [ok] {token.user} / {token.provider} / {scope}: "
                f"created={result.created} updated={result.updated} failed={result.failed}"
            )
        )
        return 1, 1 if result.failed else 0
