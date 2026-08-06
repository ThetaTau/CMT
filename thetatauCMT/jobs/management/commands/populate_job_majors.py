"""Populate the job board's `jobs.Major` vocabulary from the chapter curricula.

`ChapterCurricula` holds one row per chapter per major, so the same major
appears once for every chapter that offers it. The job board needs a single
row per major, so the import collapses those and any existing `Major` rows
that differ only by case or surrounding whitespace.

Names are stored lowercase to match `VocabularyAutocomplete.create_object`,
so a major a member types on the job form resolves to the imported row
instead of adding a near-duplicate.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from thetatauCMT.chapters.models import ChapterCurricula
from thetatauCMT.jobs.models import Major


def normalize(name):
    return " ".join((name or "").split()).lower()


class Command(BaseCommand):
    help = "Populate jobs.Major from the approved chapter curricula, lowercased and without duplicates."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )
        parser.add_argument(
            "--include-unapproved",
            action="store_true",
            help="Also import curricula still awaiting officer approval.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        merged, renamed = self.normalize_existing(dry_run)
        added = self.add_from_curricula(dry_run, options["include_unapproved"])
        self.stdout.write(f"{Major.objects.count()} major(s) currently in jobs.Major.")
        summary = f"merged {merged} duplicate(s), lowercased {renamed}, added {added} new major(s)"
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run: would have {summary}. Nothing written."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done: {summary}."))

    def normalize_existing(self, dry_run):
        """Lowercase Major names, collapsing rows that then collide into the oldest."""
        groups = {}
        for major in Major.objects.order_by("pk"):
            groups.setdefault(normalize(major.name), []).append(major)
        merged = renamed = 0
        for clean, majors in groups.items():
            keeper, extras = majors[0], majors[1:]
            if extras:
                self.stdout.write(f"  merging {len(extras)} duplicate(s) into {clean!r}")
                merged += len(extras)
            if keeper.name != clean:
                self.stdout.write(f"  renaming {keeper.name!r} to {clean!r}")
                renamed += 1
            if dry_run:
                continue
            with transaction.atomic():
                for extra in extras:
                    # Deleting the duplicate drops its own through-rows.
                    for job in extra.jobs.all():
                        job.majors.add(keeper)
                    for job_search in extra.job_searches.all():
                        job_search.majors.add(keeper)
                    extra.delete()
                if keeper.name != clean:
                    keeper.name = clean
                    keeper.save(update_fields=["name"])
        return merged, renamed

    def add_from_curricula(self, dry_run, include_unapproved):
        curricula = ChapterCurricula.objects.all()
        if not include_unapproved:
            curricula = curricula.filter(approved=True)
        names = {normalize(name) for name in curricula.values_list("major", flat=True)}
        names.discard("")
        existing = {normalize(name) for name in Major.objects.values_list("name", flat=True)}
        added = sorted(names - existing)
        for name in added:
            self.stdout.write(f"  adding {name!r}")
        if not dry_run:
            Major.objects.bulk_create([Major(name=name) for name in added])
        return len(added)
