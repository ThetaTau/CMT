"""Bulk-import legacy award winners from a CSV file (AWI-13).

Admin/server-side entry point around
:func:`thetatauCMT.awards.importer.ingest_award_csv`. Confident recipient matches
become backdated ``import`` grants; low-confidence rows land in the
``AwardImportMatchQueueItem`` queue for manual resolution in the admin UI.
Idempotent: re-running the same file never double-creates grants.

    docker exec thetataucmt_local_django \\
        python manage.py import_awards /path/to/winners.csv --user admin
"""

from django.core.management import BaseCommand, CommandError

from thetatauCMT.awards.importer import ingest_award_csv
from thetatauCMT.users.models import User


class Command(BaseCommand):
    help = "Bulk-import historical award winners from a CSV file (Admin only)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the CSV file of historical award winners.")
        parser.add_argument(
            "--user",
            help="Username of the admin performing the import (defaults to the first superuser).",
        )

    def _resolve_importer(self, username):
        if username:
            user = User.objects.filter(username=username).first()
            if user is None:
                raise CommandError(f"No user with username '{username}'.")
            return user
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            raise CommandError("No superuser found; pass --user <username>.")
        return user

    def handle(self, *args, **options):
        imported_by = self._resolve_importer(options.get("user"))
        try:
            with open(options["csv_path"], "rb") as handle:
                data = handle.read()
        except OSError as exc:
            raise CommandError(f"Could not read CSV: {exc}")

        result = ingest_award_csv(data, imported_by)
        self.stdout.write(
            self.style.SUCCESS(
                f"Import complete: {result.imported} imported, {result.duplicates} duplicate(s), "
                f"{result.queued} queued for review, {result.skipped} skipped (of {result.total} rows)."
            )
        )
        for error in result.errors:
            self.stdout.write(self.style.WARNING(f"  - {error}"))
