"""Repair historical New Member Education Program task completions.

Before the ``tasks.models.Task.mark_complete`` name-matching fix, calls made
with ``name="New Member Education Program"`` fell through to the
``create_submission = False`` branch instead of the intended "Pledge Program"
branch (the task was renamed but the string comparison was not updated). As a
result the ``TaskChapter.submission_object`` generic FK was set directly to
the raw ``forms.PledgeProgram`` instance instead of a wrapped
``submissions.Submission``. Its ``submission_id`` (the PledgeProgram's pk)
could then collide with an unrelated Submission row, so the "Related
Submission" link on the completed-task detail page could point at a totally
different chapter's/user's submission (e.g. a Risk Management Form).

This command finds affected ``TaskChapter`` rows and re-wraps them in a
proper ``Submission``, matching current ``mark_complete`` behavior.
"""

from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand

from thetatauCMT.forms.models import PledgeProgram
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.submissions.models import Submission
from thetatauCMT.tasks.models import TaskChapter


class Command(BaseCommand):
    help = (
        "Repair 'New Member Education Program' TaskChapter rows whose "
        "Related Submission points directly at a PledgeProgram instead of a "
        "wrapped Submission (fixes mis-linked 'Related Submission' links)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report affected rows without changing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        pledge_program_ct = ContentType.objects.get_for_model(PledgeProgram)
        score_type = ScoreType.objects.filter(slug="pledge-program").first()
        if score_type is None:
            self.stderr.write("ScoreType 'pledge-program' not found, aborting.")
            return

        affected = TaskChapter.objects.filter(submission_type=pledge_program_ct)
        count = affected.count()
        if not count:
            self.stdout.write("No affected TaskChapter rows found.")
            return

        self.stdout.write(f"Found {count} affected TaskChapter row(s).")
        for task_obj in affected:
            program = task_obj.submission_object
            chapter = task_obj.chapter
            self.stdout.write(
                f"  TaskChapter#{task_obj.pk} chapter={chapter} " f"program_pk={program.pk if program else None}"
            )
            if dry_run or program is None:
                continue
            submit_obj = Submission(
                user=task_obj.created_by,
                file="forms:pledge_program",
                name="Pledge program",
                type=score_type,
                chapter=chapter,
            )
            submit_obj.save(extra_info={"unmodified": program.manual != "other"})
            task_obj.submission_object = submit_obj
            task_obj.save(update_fields=["submission_type", "submission_id"])

        if dry_run:
            self.stdout.write("Dry run: no changes made.")
        else:
            self.stdout.write(f"Repaired {count} TaskChapter row(s).")
