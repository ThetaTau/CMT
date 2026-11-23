"""Everything scheduled for the Case Competition, in one daily task (Q14, NECCWI-7).

Scheduled DAILY on PythonAnywhere, in the US morning:

    python manage.py case_competition_daily

Each run sends whatever is due that day, once: the chapter reminders before a window opens,
when it opens and as it closes (only to chapters without a complete entry), the managers'
summary after a window closes, the judges' "judging is open" email and their reminders
before the judging deadline. It also gives judges any entries that reached them late (an
extension that ended). Running it again the same day sends nothing twice.

    docker exec thetataucmt_local_django python manage.py case_competition_daily --dry-run
"""

from django.core.management.base import BaseCommand

from thetatauCMT.competitions.reminders import send_scheduled


class Command(BaseCommand):
    help = "Send the Case Competition's scheduled emails and judging assignments (run daily)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be sent; send, log and change nothing.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        lines = send_scheduled(dry_run=dry_run)
        for line in lines:
            self.stdout.write(line)
        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(f"{prefix}Case Competition: {len(lines)} item(s).")
