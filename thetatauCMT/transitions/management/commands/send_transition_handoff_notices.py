"""TRWI-7: notify new officeholders that predecessor Transition Reports exist.

A SEPARATE daily command from send_transition_report_reminders (TRWI-4) --
kept independent rather than folded into that already-scheduled, production
command so nothing about its existing behavior/name changes. Meant to run
DAILY (production is PythonAnywhere, no finer-grained cron) and be a safe
no-op most days; see services.send_handoff_notices().

    docker exec thetataucmt_local_django python manage.py send_transition_handoff_notices [--dry-run]
"""

from django.core.management.base import BaseCommand

from thetatauCMT.transitions.services import send_handoff_notices


class Command(BaseCommand):
    help = "Notify new officeholders that predecessor Transition Reports are available (TRWI-7)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without sending anything or recording it.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        sent = send_handoff_notices(dry_run=dry_run)
        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(f"{prefix}Handoff notices: {sent} sent.")
