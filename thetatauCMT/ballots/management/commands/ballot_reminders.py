"""
Ballot reminders on a 7 day ladder.

Every voter is emailed when a ballot opens (from the ballot create view), then
every 7 days until they return a ballot, and once more on the due date. National
Officers are emailed individually; a chapter gets one email whose copy list
widens the longer it sits on its vote:

    day 7    Regent and Scribe
    day 14   every chapter officer
    day 21+  every chapter role holder plus the Regional Director(s)

Notes:
    Schedule this DAILY. A ballot is only emailed on the days that are an exact
    multiple of 7 from when it opened, so the ladder lands on the right day
    whatever weekday the ballot was created on, plus a final reminder on the due
    date itself.

    To test run command
        docker exec thetataucmt_local_django python manage.py ballot_reminders --dry-run
"""

from django.core.management import BaseCommand

from thetatauCMT.ballots.models import Ballot
from thetatauCMT.ballots.notifications import (
    REMINDER_INTERVAL_DAYS,
    escalation_level,
    outstanding_recipients,
    send_ballot_notifications,
)


class Command(BaseCommand):
    help = "Remind everyone who has not returned a ballot that is still open."

    def add_arguments(self, parser):
        parser.add_argument("--ballot", nargs="+", type=str, help="Limit to ballot slug(s).")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without sending any email (ignores the 7 day cadence).",
        )
        parser.add_argument(
            "--override",
            action="store_true",
            help="Send now regardless of the 7 day cadence.",
        )

    def handle(self, *args, **options):
        ballot_slugs = options.get("ballot")
        dry_run = options.get("dry_run", False)
        override = options.get("override", False)

        ballots = Ballot.open_ballots()
        if ballot_slugs:
            ballots = ballots.filter(slug__in=ballot_slugs)

        if not ballots:
            self.stdout.write("No open ballots.")
            return

        for ballot in ballots:
            days_open = ballot.days_open
            final = ballot.is_due_today
            scheduled = days_open >= REMINDER_INTERVAL_DAYS and days_open % REMINDER_INTERVAL_DAYS == 0
            if not (final or scheduled or override or dry_run):
                self.stdout.write(f"{ballot.name}: open {days_open} day(s), no reminder due; skipping.")
                continue
            level = escalation_level(days_open)
            label = "final" if final else level
            if dry_run:
                recipients = outstanding_recipients(ballot, reminder=True)
                self.stdout.write(
                    f"[dry-run] {ballot.name}: day {days_open} at '{label}' level, "
                    f"would remind {len(recipients)} voter(s)"
                )
                for recipient in recipients:
                    self.stdout.write(f"    {recipient['addressee']}: {', '.join(sorted(recipient['emails']))}")
                continue
            sent = send_ballot_notifications(ballot, reminder=True, final=final)
            self.stdout.write(f"{ballot.name}: reminded {sent} voter(s) at '{label}' level (day {days_open})")
