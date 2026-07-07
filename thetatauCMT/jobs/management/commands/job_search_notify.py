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
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from thetatauCMT.jobs.models import Job, JobSearch
from thetatauCMT.jobs.notifications import digest_since, notify_matching_searches

FREQUENCIES = {
    "daily": JobSearch.NOTIFICATION.daily.name,
    "weekly": JobSearch.NOTIFICATION.weekly.name,
}


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

    def handle(self, *args, **options):
        chosen = options["frequency"]
        override = options.get("since")
        override_dt = None
        if override:
            try:
                override_dt = timezone.datetime.fromisoformat(override)
                if timezone.is_naive(override_dt):
                    override_dt = timezone.make_aware(override_dt)
            except ValueError:
                self.stderr.write(self.style.ERROR(f"Invalid --since value: {override!r}"))
                return
        frequencies = ["daily", "weekly"] if chosen == "both" else [chosen]
        now = timezone.now()
        total_sent = 0
        for label in frequencies:
            frequency = FREQUENCIES[label]
            cutoff = override_dt or digest_since(frequency, now=now)
            job_qs = Job.get_live_jobs().filter(created__gte=cutoff)
            job_count = job_qs.count()
            search_count = JobSearch.objects.filter(notification=frequency).count()
            self.stdout.write(
                f"[{label}] cutoff={cutoff.isoformat()} live_jobs={job_count} " f"saved_searches={search_count}"
            )
            if not job_count or not search_count:
                continue
            sent = notify_matching_searches(job_qs, frequency)
            total_sent += sent
            self.stdout.write(self.style.SUCCESS(f"[{label}] sent {sent} digest email(s)"))
        self.stdout.write(self.style.SUCCESS(f"Total digest emails sent: {total_sent}"))
