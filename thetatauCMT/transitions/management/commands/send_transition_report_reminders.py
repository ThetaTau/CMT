"""TRWI-4: send Transition Report reminder emails (both mechanisms).

Meant to run DAILY (production is PythonAnywhere, which has no finer-grained
cron -- see region_officer_reminder_digest.py) and be a safe no-op most days;
see services.send_transition_report_reminders() for both mechanisms:

1. Per-officer reminders at configured due-date offsets, escalating to the
   Regent (past due) and Regional Director (further past due).
2. A once-per-semester broadcast to everyone with an open obligation.

    docker exec thetataucmt_local_django python manage.py send_transition_report_reminders [--dry-run]
"""

from django.core.management.base import BaseCommand

from thetatauCMT.transitions.services import send_transition_report_reminders


class Command(BaseCommand):
    help = "Send Transition Report reminder emails (TRWI-4)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without sending anything or recording it.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        counts = send_transition_report_reminders(dry_run=dry_run)
        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            f"{prefix}Reminders: {counts['due_date_reminders_sent']} due-date reminder(s), "
            f"{counts['seasonal_reminders_sent']} seasonal reminder(s)."
        )
