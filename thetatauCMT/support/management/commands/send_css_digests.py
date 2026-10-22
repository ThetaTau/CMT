"""Send the Chapter Support Specialist digests (CSSWI-6; Q14, Q25 C).

PythonAnywhere only runs daily tasks, so schedule both DAILY:

    python manage.py send_css_digests --period daily
    python manage.py send_css_digests --period monthly    # sends on the 1st

Either one can run twice without sending twice.

    docker exec thetataucmt_local_django python manage.py send_css_digests --period daily --dry-run
"""

from django.core.management import BaseCommand
from django.utils import timezone

from thetatauCMT.support.digests import send_daily_digests, send_monthly_digests


class Command(BaseCommand):
    help = "Send Chapter Support Specialists their daily or monthly chapter digest."

    def add_arguments(self, parser):
        parser.add_argument("--period", choices=["daily", "monthly"], required=True)
        parser.add_argument("--dry-run", action="store_true", help="Report only; send nothing and mark nothing.")
        parser.add_argument(
            "--day",
            type=int,
            default=1,
            help="Day of the month the monthly digest sends on when scheduled daily (default 1).",
        )
        parser.add_argument("--override", action="store_true", help="Send the monthly digest on any day.")
        parser.add_argument(
            "--force", action="store_true", help="Send the monthly digest again to people who already got it."
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        prefix = "[dry-run] Would send" if dry_run else "Sent"
        if options["period"] == "daily":
            count = send_daily_digests(dry_run=dry_run)
            self.stdout.write(f"{prefix} {count} daily digest(s).")
            return
        today = timezone.localdate()
        day = options["day"]
        if day and today.day != day and not (options["override"] or dry_run):
            self.stdout.write(f"Not the scheduled day (the monthly digest sends on day {day}); skipping.")
            return
        count = send_monthly_digests(today=today, dry_run=dry_run, force=options["force"])
        self.stdout.write(f"{prefix} {count} monthly digest(s).")
