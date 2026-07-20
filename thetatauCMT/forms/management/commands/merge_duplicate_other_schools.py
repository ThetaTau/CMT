"""Merge fuzzy-duplicate `OtherSchool` records.

The data migration in `forms/0043_otherschool` deduplicates on a
normalized key (case-fold + whitespace collapse + trailing-punctuation
strip). Anything more aggressive is unsafe to run unattended because
false merges are permanent. This command lets an operator interactively
(or with `--yes`) collapse remaining fuzzy duplicates via
`difflib.SequenceMatcher`.

`OtherSchool` names that duplicate an existing `Chapter.school` are also
reported and, on merge, their `StatusChange` rows are repointed at the
matching `Chapter` via the sibling `new_school` FK (the `OtherSchool`
row is then deleted).

Examples::

    podman exec thetataucmt_local_django python manage.py \\
        merge_duplicate_other_schools --dry-run

    podman exec thetataucmt_local_django python manage.py \\
        merge_duplicate_other_schools --threshold 0.92 --yes
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from django.core.management.base import BaseCommand
from django.db import transaction

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.forms.models import OtherSchool, StatusChange


def _normalize(name: str) -> str:
    s = (name or "").casefold()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


class Command(BaseCommand):
    help = (
        "Merge fuzzy-duplicate OtherSchool records and reassign any that "
        "match an existing Chapter.school back onto the Chapter FK."
    )

    def add_arguments(self, parser):
        parser.add_argument("--threshold", type=float, default=0.90)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--yes", action="store_true", help="Skip confirmation")

    def handle(self, *args, **opts):
        threshold: float = opts["threshold"]
        dry_run: bool = opts["dry_run"]
        skip_confirm: bool = opts["yes"]

        if not (0.0 < threshold <= 1.0):
            self.stderr.write("--threshold must be between 0 and 1")
            return

        # ---- Pass 1: any OtherSchool that duplicates a Chapter.school ----
        chapters_by_key = {_normalize(s): pk for pk, s in Chapter.objects.values_list("pk", "school") if s}
        chapter_reassigns: list[tuple[OtherSchool, int]] = []
        for os_ in OtherSchool.objects.all():
            chapter_pk = chapters_by_key.get(_normalize(os_.name))
            if chapter_pk is not None:
                chapter_reassigns.append((os_, chapter_pk))

        # ---- Pass 2: fuzzy duplicates within OtherSchool ----
        remaining = list(OtherSchool.objects.exclude(pk__in=[os_.pk for os_, _ in chapter_reassigns]).order_by("name"))
        merges: list[tuple[OtherSchool, list[OtherSchool]]] = []
        assigned: set[int] = set()
        for i, a in enumerate(remaining):
            if a.pk in assigned:
                continue
            group = [a]
            for b in remaining[i + 1 :]:
                if b.pk in assigned:
                    continue
                if _similar(a.name, b.name) >= threshold:
                    group.append(b)
            if len(group) > 1:
                canonical = max(group, key=lambda o: (len(o.name), o.name))
                dupes = [o for o in group if o.pk != canonical.pk]
                for o in group:
                    assigned.add(o.pk)
                merges.append((canonical, dupes))
            else:
                assigned.add(a.pk)

        if not chapter_reassigns and not merges:
            self.stdout.write(self.style.SUCCESS("No fuzzy duplicates found."))
            return

        for os_, chapter_pk in chapter_reassigns:
            n = StatusChange.objects.filter(new_school_other=os_).count()
            chapter = Chapter.objects.get(pk=chapter_pk)
            self.stdout.write(
                f"Chapter match: {os_.name!r} → chapter {chapter.name!r} "
                f"({n} status changes will move to new_school FK)"
            )

        for canonical, dupes in merges:
            self.stdout.write(f"\nKeep OtherSchool: {canonical.name!r}")
            for d in dupes:
                affected = StatusChange.objects.filter(new_school_other=d).count()
                self.stdout.write(
                    f"  merge <- {d.name!r} "
                    f"(similarity {_similar(canonical.name, d.name):.2f}, "
                    f"{affected} status changes affected)"
                )

        total_dupes = sum(len(d) for _, d in merges)
        self.stdout.write(
            f"\n{len(chapter_reassigns)} chapter-match(es); "
            f"{len(merges)} fuzzy group(s) with {total_dupes} duplicate(s)."
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes made."))
            return

        if not skip_confirm:
            answer = input("Proceed? [y/N] ")
            if answer.strip().lower() != "y":
                self.stdout.write("Aborted.")
                return

        with transaction.atomic():
            for os_, chapter_pk in chapter_reassigns:
                StatusChange.objects.filter(new_school_other=os_).update(
                    new_school_id=chapter_pk,
                    new_school_other=None,
                )
                os_.delete()
            for canonical, dupes in merges:
                dupe_pks = [d.pk for d in dupes]
                StatusChange.objects.filter(new_school_other_id__in=dupe_pks).update(new_school_other=canonical)
                OtherSchool.objects.filter(pk__in=dupe_pks).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Reassigned {len(chapter_reassigns)} to chapters; " f"merged {total_dupes} fuzzy duplicate(s)."
            )
        )
