"""Merge fuzzy-duplicate `Employer` records.

The initial data migration (`forms/0044_employer`) deduplicates on a
normalized key (case-fold + whitespace collapse + trailing punctuation
and legal-suffix stripping). Anything more aggressive is unsafe to run
unattended because false merges are permanent. This command lets an
operator interactively (or with `--yes`) collapse remaining fuzzy
duplicates via `difflib.SequenceMatcher`.

Examples::

    # Preview at the default 0.90 similarity threshold
    podman exec thetataucmt_local_django python manage.py \\
        merge_duplicate_employers --dry-run

    # Merge without prompt (CI / scripted use)
    podman exec thetataucmt_local_django python manage.py \\
        merge_duplicate_employers --threshold 0.92 --yes
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from django.core.management.base import BaseCommand
from django.db import transaction

from thetatauCMT.forms.models import Employer, StatusChange

_SUFFIX_RE = re.compile(
    r",?\s*(inc|incorporated|llc|l\.l\.c\.|corp|corporation|co|company|" r"ltd|limited|plc|llp|lp|gmbh)\.?$",
    re.IGNORECASE,
)


def _normalize(name: str) -> str:
    s = (name or "").casefold()
    s = _SUFFIX_RE.sub("", s)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


class Command(BaseCommand):
    help = "Merge fuzzy-duplicate Employer records; repoints StatusChange rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold",
            type=float,
            default=0.90,
            help="difflib similarity ratio required to consider two employer names "
            "duplicates (0.0-1.0, default 0.90).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show proposed merges without changing any data.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip interactive confirmation prompt.",
        )

    def handle(self, *args, **opts):
        threshold: float = opts["threshold"]
        dry_run: bool = opts["dry_run"]
        skip_confirm: bool = opts["yes"]

        if not (0.0 < threshold <= 1.0):
            self.stderr.write("--threshold must be between 0 and 1")
            return

        employers = list(Employer.objects.order_by("name"))
        n = len(employers)
        self.stdout.write(f"Scanning {n} employers for similarity >= {threshold:.2f}...")

        # Simple O(n^2) sweep. For a few thousand rows this is fine as a
        # one-off cleanup command. Group members are chosen greedily around
        # the first-encountered representative.
        merges: list[tuple[Employer, list[Employer]]] = []
        assigned: set[int] = set()
        for i, a in enumerate(employers):
            if a.pk in assigned:
                continue
            group = [a]
            for b in employers[i + 1 :]:
                if b.pk in assigned:
                    continue
                if _similar(a.name, b.name) >= threshold:
                    group.append(b)
            if len(group) > 1:
                # Prefer the longest name (usually most detail) as canonical.
                canonical = max(group, key=lambda e: (len(e.name), e.name))
                dupes = [e for e in group if e.pk != canonical.pk]
                for e in group:
                    assigned.add(e.pk)
                merges.append((canonical, dupes))
            else:
                assigned.add(a.pk)

        if not merges:
            self.stdout.write(self.style.SUCCESS("No fuzzy duplicates found."))
            return

        total_dupes = sum(len(d) for _, d in merges)
        for canonical, dupes in merges:
            self.stdout.write(f"\nKeep: {canonical.name!r}")
            for d in dupes:
                affected = StatusChange.objects.filter(employer=d).count()
                self.stdout.write(
                    f"  merge <- {d.name!r} "
                    f"(similarity {_similar(canonical.name, d.name):.2f}, "
                    f"{affected} status changes affected)"
                )

        self.stdout.write(f"\n{len(merges)} group(s), {total_dupes} duplicate(s).")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run, no changes made."))
            return

        if not skip_confirm:
            answer = input(f"Proceed with merging {total_dupes} employers? [y/N] ")
            if answer.strip().lower() != "y":
                self.stdout.write("Aborted.")
                return

        with transaction.atomic():
            for canonical, dupes in merges:
                dupe_pks = [d.pk for d in dupes]
                StatusChange.objects.filter(employer_id__in=dupe_pks).update(employer=canonical)
                Employer.objects.filter(pk__in=dupe_pks).delete()

        self.stdout.write(self.style.SUCCESS(f"Merged {total_dupes} duplicate employer(s)."))
