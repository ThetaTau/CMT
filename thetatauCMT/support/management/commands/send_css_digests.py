"""Send the Chapter Support Specialist digests (CSSWI-6; Q14, Q25 C).

One task, scheduled DAILY on PythonAnywhere:

    python manage.py send_css_digests

Every run sends the daily digest; on the 1st of the month it also sends the monthly digest
(``--day`` picks another day). Running it again sends nothing twice. ``--period daily`` or
``--period monthly`` limits a manual run to one digest; ``--period both`` is the default.

    docker exec thetataucmt_local_django python manage.py send_css_digests --dry-run
"""

from django.core.management import BaseCommand
from django.utils import timezone

from thetatauCMT.support.digests import send_daily_digests, send_monthly_digests


class Command(BaseCommand):
    help = "Send Chapter Support Specialists their daily digest, and on the 1st their monthly digest."

    def add_arguments(self, parser):
        parser.add_argument(
            "--period",
            choices=["daily", "monthly", "both"],
            default="both",
            help="Which digest to send. Defaults to both: the daily one every run, the monthly one on --day.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report only; send nothing and mark nothing (also ignores the day of the month).",
        )
        parser.add_argument(
            "--day",
            type=int,
            default=1,
            help="Day of the month the monthly digest sends on (default 1).",
        )
        parser.add_argument("--override", action="store_true", help="Send the monthly digest whatever the day.")
        parser.add_argument(
            "--force", action="store_true", help="Send the monthly digest again to people who already got it."
        )

    def handle(self, *args, **options):
        period = options["period"]
        dry_run = options["dry_run"]
        prefix = "[dry-run] Would send" if dry_run else "Sent"
        if period in ("daily", "both"):
            count = send_daily_digests(dry_run=dry_run)
            self.stdout.write(f"{prefix} {count} daily digest(s).")
        if period in ("monthly", "both"):
            self._send_monthly(options, prefix)

    def _send_monthly(self, options, prefix):
        today = timezone.localdate()
        day = options["day"]
        if day and today.day != day and not (options["override"] or options["dry_run"]):
            self.stdout.write(f"Not the monthly digest's day (it sends on day {day}); skipping it.")
            return
        count = send_monthly_digests(today=today, dry_run=options["dry_run"], force=options["force"])
        self.stdout.write(f"{prefix} {count} monthly digest(s).")
