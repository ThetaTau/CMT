"""Archive (retire) old ``TaskDate`` due dates.

Retired dates are marked ``archived=True`` so they no longer appear as
incomplete work for chapters and can no longer be completed. This keeps the
task list focused on current, actionable work.

Examples::

    # Archive everything due before the current academic year (default)
    python manage.py archive_old_task_dates

    # Archive everything due before an explicit date
    python manage.py archive_old_task_dates --before 2024-07-01

    # Archive dates older than 365 days
    python manage.py archive_old_task_dates --older-than-days 365

    # Preview only, restrict to one task by name
    python manage.py archive_old_task_dates --task "Audit" --dry-run
"""

from datetime import datetime, timedelta

from django.core.management import BaseCommand
from django.utils import timezone

from core.models import academic_encompass_start_end_date
from thetatauCMT.tasks.models import TaskDate


class Command(BaseCommand):
    help = "Mark old TaskDate due dates as no longer needed (archived)."

    def add_arguments(self, parser):
        cutoff = parser.add_mutually_exclusive_group()
        cutoff.add_argument(
            "--before",
            type=str,
            default=None,
            help="Archive dates strictly before this YYYY-MM-DD date.",
        )
        cutoff.add_argument(
            "--older-than-days",
            type=int,
            default=None,
            help="Archive dates whose due date is more than N days ago.",
        )
        parser.add_argument(
            "--task",
            type=str,
            default=None,
            help="Only archive dates for the Task with this exact name.",
        )
        parser.add_argument(
            "--reason",
            type=str,
            default="Retired: older than the current academic year",
            help="Reason stored on each archived date.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be archived without changing anything.",
        )

    def _resolve_cutoff(self, options):
        if options["before"]:
            try:
                return datetime.strptime(options["before"], "%Y-%m-%d").date()
            except ValueError:
                raise ValueError(f"Invalid --before date {options['before']!r}; expected YYYY-MM-DD.")
        if options["older_than_days"] is not None:
            return timezone.localdate() - timedelta(days=options["older_than_days"])
        # Default: the start of the current academic year.
        academic_start, _ = academic_encompass_start_end_date()
        return academic_start.date()

    def handle(self, *args, **options):
        cutoff = self._resolve_cutoff(options)
        qs = TaskDate.objects.filter(archived=False, date__lt=cutoff)
        if options["task"]:
            qs = qs.filter(task__name=options["task"])

        count = qs.count()
        self.stdout.write(f"Found {count} active due date(s) before {cutoff}.")

        if options["dry_run"]:
            for task_date in qs.order_by("date")[:50]:
                self.stdout.write(f"  would archive: {task_date}")
            if count > 50:
                self.stdout.write(f"  ... and {count - 50} more")
            self.stdout.write(self.style.WARNING("Dry run — nothing changed."))
            return

        updated = qs.update(
            archived=True,
            archived_on=timezone.now(),
            archived_reason=options["reason"],
        )
        self.stdout.write(self.style.SUCCESS(f"Archived {updated} due date(s)."))
