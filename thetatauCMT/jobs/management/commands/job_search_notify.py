"""Send daily / weekly JobSearch digest emails.

Notes:
    Trigger with:
        podman exec thetataucmt_local_django python manage.py job_search_notify --frequency daily
        podman exec thetataucmt_local_django python manage.py job_search_notify --frequency weekly

    ``--frequency both`` (the default) runs both.

    The command finds every ``Job`` that is currently live and was created
    within the frequency window (last 24 hours for daily, last 7 days for
    weekly), then emails each ``JobSearch`` owner whose saved search
    matches at least one of those jobs.

    PythonAnywhere only offers *daily* scheduled tasks, so (like
    ``region_officer_reminder_digest`` / ``award_digest``) the weekly digest
    self-gates to a single weekday (Wednesday by default). Schedule this
    command DAILY with ``--frequency both``; the daily digest sends every
    run and the weekly digest only sends on ``--weekday``.

    ``--override`` sends the weekly digest right now regardless of the
    weekday gate. ``--dry-run`` reports what would be sent without sending
    any email, and also bypasses the weekday gate so it can be tested any
    day:
        podman exec thetataucmt_local_django python manage.py job_search_notify --dry-run
"""

import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from thetatauCMT.jobs.models import Job, JobSearch
from thetatauCMT.jobs.notifications import digest_since, notify_matching_searches

FREQUENCIES = {
    "daily": JobSearch.NOTIFICATION.daily.name,
    "weekly": JobSearch.NOTIFICATION.weekly.name,
}
WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Command(BaseCommand):
    help = (
        "Send JobSearch digest emails to members subscribed to daily and/or weekly "
        "notifications for saved searches that match jobs created in the window."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--frequency",
            choices=["daily", "weekly", "both"],
            default="both",
            help="Which digest to send. Defaults to both.",
        )
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help=(
                "ISO-8601 datetime override for the 'created since' cutoff. "
                "When set, the same cutoff is applied to each frequency selected."
            ),
        )
        parser.add_argument(
            "--weekday",
            type=int,
            default=2,
            help=(
                "Weekday the weekly digest actually sends on when this command is run daily "
                "(0=Monday ... 6=Sunday). Default Wednesday. The daily digest ignores this."
            ),
        )
        parser.add_argument(
            "--override",
            action="store_true",
            help="Send the weekly digest now regardless of the weekday gate.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without sending any email (also bypasses the weekday gate).",
        )

    def handle(self, *args, **options):
        chosen = options["frequency"]
        since = options.get("since")
        weekday = options.get("weekday", 2)
        override = options.get("override", False)
        dry_run = options.get("dry_run", False)
        since_dt = None
        if since:
            try:
                since_dt = timezone.datetime.fromisoformat(since)
                if timezone.is_naive(since_dt):
                    since_dt = timezone.make_aware(since_dt)
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid --since value: {since!r}"))
                return
        frequencies = ["daily", "weekly"] if chosen == "both" else [chosen]
        now = timezone.now()
        today_weekday = datetime.date.today().weekday()
        total_sent = 0
        for label in frequencies:
            frequency = FREQUENCIES[label]
            # PythonAnywhere runs this daily; only actually send the weekly
            # digest on the configured weekday so subscribers get one email a
            # week. --override / --dry-run bypass the gate; daily is unaffected.
            if label == "weekly" and today_weekday != weekday and not (override or dry_run):
                self.stdout.write(
                    f"[{label}] Not the scheduled day (today is {WEEKDAY_NAMES[today_weekday]}, "
                    f"weekly digest runs on {WEEKDAY_NAMES[weekday]}); skipping."
                )
                continue
            cutoff = since_dt or digest_since(frequency, now=now)
            job_qs = Job.get_live_jobs().filter(created__gte=cutoff)
            job_count = job_qs.count()
            search_count = JobSearch.objects.filter(notification=frequency).count()
            self.stdout.write(
                f"[{label}] cutoff={cutoff.isoformat()} live_jobs={job_count} " f"saved_searches={search_count}"
            )
            if not job_count or not search_count:
                continue
            sent = notify_matching_searches(job_qs, frequency, dry_run=dry_run)
            total_sent += sent
            verb = "would send" if dry_run else "sent"
            style = self.style.WARNING if dry_run else self.style.SUCCESS
            self.stdout.write(style(f"[{label}] {verb} {sent} digest email(s)"))
        verb = "would send" if dry_run else "sent"
        self.stdout.write(self.style.SUCCESS(f"Total digest emails {verb}: {total_sent}"))
