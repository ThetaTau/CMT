"""
Weekly Regional Director digest of chapters needing officer updates.

Sends ONE summary email per region to that region's Regional Directors (and the
region mailbox) listing every active chapter that still has an expiring or
missing officer on the CMT. This replaces the per-chapter daily cc that used to
land on the RD for the ``officer_update_reminder_email`` command, so an
unresponsive chapter no longer emails the RD every day while the RD still gets a
regular prompt to follow up.

Notes:
    PythonAnywhere only offers *daily* scheduled tasks, so — like
    ``monthly_chapter_officer_email`` (which self-gates to the 1st of the
    month) — this command is meant to be scheduled DAILY and gates itself to a
    single weekday (Monday by default). Run it daily; it only emails once a
    week.

    To test run command
        docker-compose -f local.yml run --rm django python manage.py region_officer_reminder_digest --dry-run
"""

import datetime

from django.core.management import BaseCommand

from thetatauCMT.regions.models import Region
from thetatauCMT.users.notifications import RegionalDirectorOfficerDigest

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class Command(BaseCommand):
    help = "Send Regional Directors a weekly summary of chapters that need officer updates on the CMT."

    def add_arguments(self, parser):
        parser.add_argument("--region", nargs="+", type=str, help="Limit to region slug(s).")
        parser.add_argument("--chapter", nargs="+", type=str, help="Limit to chapter slug(s).")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without sending any email (ignores the weekday gate).",
        )
        parser.add_argument(
            "--override",
            action="store_true",
            help="Send now regardless of the weekday gate.",
        )
        parser.add_argument(
            "--weekday",
            type=int,
            default=0,
            help="Weekday to send on when scheduled daily (0=Monday ... 6=Sunday). Default Monday.",
        )

    def handle(self, *args, **options):
        region_slugs = options.get("region")
        chapter_slugs = options.get("chapter")
        dry_run = options.get("dry_run", False)
        override = options.get("override", False)
        weekday = options.get("weekday", 0)

        # PythonAnywhere runs this daily; only actually send on the chosen
        # weekday so the RD gets one email per week (mirrors the monthly
        # command's ``today == 1`` gate). --override / --dry-run bypass the gate.
        today_weekday = datetime.date.today().weekday()
        if today_weekday != weekday and not (override or dry_run):
            self.stdout.write(
                f"Not the scheduled day (today is {WEEKDAY_NAMES[today_weekday]}, "
                f"digest runs on {WEEKDAY_NAMES[weekday]}); skipping."
            )
            return

        regions = Region.objects.all()
        if region_slugs:
            regions = regions.filter(slug__in=region_slugs)

        for region in regions:
            chapters = region.chapters.exclude(active=False)
            if chapter_slugs:
                chapters = chapters.filter(slug__in=chapter_slugs)

            chapter_updates = []
            for chapter in chapters:
                _, officers_to_update = chapter.get_about_expired_coucil()
                if officers_to_update:
                    chapter_updates.append({"chapter": chapter, "officers": ", ".join(officers_to_update)})

            if not chapter_updates:
                self.stdout.write(f"{region.name}: no chapters need officer updates")
                continue

            if dry_run:
                self.stdout.write(
                    f"[dry-run] {region.name}: would notify {len(chapter_updates)} chapter(s): "
                    + ", ".join(update["chapter"].name for update in chapter_updates)
                )
                continue

            result = RegionalDirectorOfficerDigest(region, chapter_updates).send()
            self.stdout.write(f"{region.name}: sent digest for {len(chapter_updates)} chapter(s) -> {result}")
