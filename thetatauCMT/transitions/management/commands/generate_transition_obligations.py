"""TRWI-3: generate/refresh ReportObligation rows from officer term ends.

Meant to run DAILY (production is PythonAnywhere, which has no finer-grained
cron -- see region_officer_reminder_digest.py) and be a safe no-op most days;
see services.generate_obligations() for the two-trigger generation algorithm
and the same-run missed-marking pass.

    docker exec thetataucmt_local_django python manage.py generate_transition_obligations [--dry-run] [--lookahead-days N]
"""

from django.core.management.base import BaseCommand

from thetatauCMT.transitions.services import generate_obligations


class Command(BaseCommand):
    help = "Generate/refresh Transition Report obligations from officer term ends (TRWI-3)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without writing anything.",
        )
        parser.add_argument(
            "--lookahead-days",
            type=int,
            default=None,
            help=(
                "How far ahead to scan officer term ends. Default: derived from the "
                "due-date offset + largest reminder offset + a buffer "
                "(services.get_default_lookahead_days())."
            ),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        counts = generate_obligations(lookahead_days=options["lookahead_days"], dry_run=dry_run)
        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}Obligations: {counts['term_end_created']} created from term ends, "
            f"{counts['vacant_created']} created for already-vacant positions, "
            f"{counts['missed']} marked missed."
        )
