"""Monthly award digest command (AWI-9).

Aggregates a calendar month's granted awards into one digest email to the
configured audience. Idempotent: a period that already has an
``AwardDigestRun`` is skipped unless ``--force`` is given.

Schedule DAILY on PythonAnywhere and gate to the 1st of the month, or run
manually with ``--year``/``--month``.

    docker exec thetataucmt_local_django python manage.py award_digest --dry-run
"""

import datetime

from django.core.management import BaseCommand

from core.models import month_period, previous_month_period
from thetatauCMT.awards.digest import send_award_digest


class Command(BaseCommand):
    help = "Send the monthly award digest email to the configured audience."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, help="Digest year (with --month).")
        parser.add_argument("--month", type=int, help="Digest month 1-12 (with --year).")
        parser.add_argument("--force", action="store_true", help="Re-send even if this period was already digested.")
        parser.add_argument("--dry-run", action="store_true", help="Report only; do not send or record a run.")
        parser.add_argument(
            "--day",
            type=int,
            default=1,
            help="Day of month to actually send on when scheduled daily (default 1). Use 0 to disable the gate.",
        )
        parser.add_argument("--override", action="store_true", help="Send regardless of the day-of-month gate.")

    def handle(self, *args, **options):
        year = options.get("year")
        month = options.get("month")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)
        day = options.get("day", 1)
        override = options.get("override", False)

        if year and month:
            period_start, period_end = month_period(year, month)
        else:
            # Scheduled daily; only run on the chosen day-of-month (default 1)
            # unless overridden. Digests the previous calendar month.
            if day and datetime.date.today().day != day and not (override or dry_run):
                self.stdout.write(f"Not the scheduled day (runs on day {day}); skipping.")
                return
            period_start, period_end = previous_month_period()

        run = send_award_digest(period_start, period_end, force=force, dry_run=dry_run)
        if dry_run:
            self.stdout.write(f"[dry-run] Would digest {period_start} to {period_end}.")
        elif run is None:
            self.stdout.write(f"Period {period_start} to {period_end} already digested; skipping (use --force).")
        else:
            self.stdout.write(f"Sent award digest for {period_start} to {period_end} ({run.grant_count} awards).")
