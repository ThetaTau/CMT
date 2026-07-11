"""Run the weekly auto-sync for every token that has enrolled scopes.

Typical schedule: once a week via cron / PythonAnywhere / Celery beat. This
command is safe to run more often — it does nothing for a token whose
``auto_sync_scopes`` list is empty.

Usage::

    podman exec thetataucmt_local_django python manage.py weekly_contact_sync
    podman exec thetataucmt_local_django python manage.py weekly_contact_sync --user someone@example.com
    podman exec thetataucmt_local_django python manage.py weekly_contact_sync --dry-run
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from thetatauCMT.contact_sync.models import UserContactSyncToken
from thetatauCMT.contact_sync.officers import collect_contacts_for_scope
from thetatauCMT.contact_sync.providers import get_provider, provider_is_configured
from thetatauCMT.contact_sync.providers.base import ProviderAuthError, ProviderNotConfigured


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
            help="Print what would happen without actually pushing.",
        )

    def handle(self, *args, **options) -> None:  # noqa: ANN401
        qs = (
            UserContactSyncToken.objects.exclude(auto_sync_scopes__len=0)
            .select_related("user")
            .order_by("provider", "user_id")
        )
        if options.get("user"):
            qs = qs.filter(user__email__iexact=options["user"]) | qs.filter(user__username__iexact=options["user"])
        if options.get("provider"):
            qs = qs.filter(provider=options["provider"])
        dry_run = options.get("dry_run", False)

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
