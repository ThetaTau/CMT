"""Load the curated job board major list from ``jobs/fixtures/job_majors.json``.

Each fixture entry is a canonical major plus the spellings seen in the wild
(typos, ampersands, degree suffixes, department names) that should collapse
into it. Rows already tagged on a job, a saved search, or a member's final
major are repointed at the canonical row before the duplicate is removed.

Names are stored lowercase to match `VocabularyAutocomplete.create_object`,
so a major a member types on the job form resolves to the curated row
instead of adding a near-duplicate.

Majors in the database but absent from the fixture are reported, never
deleted: they may be legitimate entries a member added.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from thetatauCMT.jobs.models import Major

DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "fixtures" / "job_majors.json"


def normalize(name):
    return " ".join((name or "").split()).lower()


class Command(BaseCommand):
    help = "Load the curated major list into jobs.Major, merging known spelling variants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )
        parser.add_argument(
            "--path",
            default=str(DEFAULT_PATH),
            help="Major fixture to load. Defaults to the one packaged with the jobs app.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        canonicals, alias_map = self.load_fixture(Path(options["path"]))
        groups, unmatched = self.group_existing(alias_map)
        created = merged = renamed = 0
        for canonical in canonicals:
            rows = groups.get(canonical, [])
            if not rows:
                created += 1
                self.stdout.write(f"  adding {canonical!r}")
                if not dry_run:
                    Major.objects.create(name=canonical)
                continue
            # Prefer a row already named correctly so tagged jobs keep their pk.
            keeper = next((row for row in rows if normalize(row.name) == canonical), rows[0])
            extras = [row for row in rows if row.pk != keeper.pk]
            for extra in extras:
                self.stdout.write(f"  merging {extra.name!r} into {canonical!r}")
            merged += len(extras)
            if keeper.name != canonical:
                self.stdout.write(f"  renaming {keeper.name!r} to {canonical!r}")
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
                    for member in extra.members.all():
                        member.major_final.add(keeper)
                    extra.delete()
                if keeper.name != canonical:
                    keeper.name = canonical
                    keeper.save(update_fields=["name"])
        for major in unmatched:
            self.stdout.write(self.style.WARNING(f"  kept, not in fixture: {major.name!r}"))
        summary = (
            f"added {created}, merged {merged} duplicate(s), renamed {renamed}, "
            f"left {len(unmatched)} major(s) not in the fixture"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry run: would have {summary}. Nothing written."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Done: {summary}."))

    def load_fixture(self, path):
        """Return the canonical names in fixture order and a spelling to canonical map."""
        if not path.exists():
            raise CommandError(f"Major fixture not found: {path}")
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CommandError(f"{path} is not valid JSON: {exc}")
        if not isinstance(entries, list):
            raise CommandError(f"{path} must hold a list of majors")
        canonicals, alias_map = [], {}
        for entry in entries:
            canonical = normalize(entry.get("name"))
            if not canonical:
                raise CommandError(f"{path} has an entry with no name: {entry!r}")
            canonicals.append(canonical)
            for spelling in [canonical] + [normalize(alias) for alias in entry.get("aliases", [])]:
                if spelling in alias_map and alias_map[spelling] != canonical:
                    raise CommandError(f"{path} maps {spelling!r} to both {alias_map[spelling]!r} and {canonical!r}")
                alias_map[spelling] = canonical
        return canonicals, alias_map

    def group_existing(self, alias_map):
        """Bucket existing Major rows by the canonical name they belong to."""
        groups, unmatched = {}, []
        for major in Major.objects.order_by("pk"):
            canonical = alias_map.get(normalize(major.name))
            if canonical is None:
                unmatched.append(major)
            else:
                groups.setdefault(canonical, []).append(major)
        return groups, unmatched
