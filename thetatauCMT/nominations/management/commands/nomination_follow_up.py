"""VWI-11: daily follow-up re-contact for stalled volunteer nominations.

Run daily (cron / PythonAnywhere / Celery beat):

    python manage.py nomination_follow_up [--dry-run] [--interval-months N]

Finds nominations that are still awaiting the nominee's response, or parked
"follow up later", with no reply / no movement for >= the follow-up interval
(default 6 months, from the config system), and re-contacts them: a fresh
tokenized consent link is issued and emailed. ``last_contacted`` is updated so
each nomination re-fires only after the next interval (repeat every 6 months
while unanswered). Idempotent within an interval; skips nominations that have
moved on or are marked not-interested.
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from thetatauCMT.nominations.services import (
    get_follow_up_interval_months,
    nominations_awaiting_follow_up,
    nominations_awaiting_response,
    recontact_nomination,
    resend_consent_request,
)


class Command(BaseCommand):
    help = "Re-contact nominations stalled awaiting a nominee response / follow-up."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be re-contacted without sending anything.",
        )
        parser.add_argument(
            "--interval-months",
            type=int,
            default=None,
            help="Override the re-contact interval (default from config, 6).",
        )

    def handle(self, *args, **options):
        interval = options["interval_months"] or get_follow_up_interval_months()
        cutoff = timezone.now() - datetime.timedelta(days=30 * interval)
        dry_run = options["dry_run"]

        count = 0
        for nomination in list(nominations_awaiting_follow_up(before=cutoff)):
            if nomination.not_interested:
                continue
            if not dry_run:
                recontact_nomination(nomination)
            count += 1
            self.stdout.write(f"Re-contacted (follow-up): #{nomination.pk} {nomination.nominee_display}")

        for nomination in list(nominations_awaiting_response(before=cutoff)):
            if nomination.not_interested:
                continue
            if not dry_run:
                resend_consent_request(nomination)
            count += 1
            self.stdout.write(f"Re-contacted (awaiting response): #{nomination.pk} {nomination.nominee_display}")

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(f"{prefix}Re-contacted {count} nomination(s) not answered in >= {interval} months.")
