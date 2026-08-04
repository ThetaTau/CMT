"""Merge fuzzy-duplicate :class:`~thetatauCMT.users.models.Organization` records.

The initial data migration (``users/0040_organization``) deduplicates existing
free-text org names on a normalized key (case-fold + whitespace collapse +
punctuation stripping). Anything more aggressive is unsafe to run unattended
because false merges are permanent. This command lets an operator interactively
(or with ``--yes``) collapse remaining fuzzy duplicates via
``difflib.SequenceMatcher`` — the same approach used by
``merge_duplicate_employers``.

Examples::

    # Preview at the default 0.90 similarity threshold
    docker exec thetataucmt_local_django python manage.py \\
        merge_duplicate_organizations --dry-run

    # Merge without prompt (CI / scripted use)
    docker exec thetataucmt_local_django python manage.py \\
        merge_duplicate_organizations --threshold 0.92 --yes
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from django.core.management.base import BaseCommand
from django.db import transaction

from thetatauCMT.users.models import Organization, UserOrgParticipate

# Trailing generic org words that should not by themselves make two
# organization names look distinct (e.g. "Robotics" vs "Robotics Club").
_SUFFIX_RE = re.compile(
    r",?\s*(society|association|organization|org|club|chapter|honorary|"
    r"honor society|fraternity|sorority|professional society)\.?$",
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
    help = "Merge fuzzy-duplicate Organization records; repoints UserOrgParticipate rows."

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold",
            type=float,
            default=0.90,
            help="difflib similarity ratio required to consider two organization names "
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

        organizations = list(Organization.objects.order_by("name"))
        n = len(organizations)
        self.stdout.write(f"Scanning {n} organizations for similarity >= {threshold:.2f}...")

        # Simple O(n^2) sweep. For a few thousand rows this is fine as a
        # one-off cleanup command. Group members are chosen greedily around
        # the first-encountered representative.
        merges: list[tuple[Organization, list[Organization]]] = []
        assigned: set[int] = set()
        for i, a in enumerate(organizations):
            if a.pk in assigned:
                continue
            group = [a]
            for b in organizations[i + 1 :]:
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
                affected = UserOrgParticipate.objects.filter(organization=d).count()
                self.stdout.write(
                    f"  merge <- {d.name!r} "
                    f"(similarity {_similar(canonical.name, d.name):.2f}, "
                    f"{affected} participations affected)"
                )

        self.stdout.write(f"\n{len(merges)} group(s), {total_dupes} duplicate(s).")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run, no changes made."))
            return

        if not skip_confirm:
            answer = input(f"Proceed with merging {total_dupes} organizations? [y/N] ")
            if answer.strip().lower() != "y":
                self.stdout.write("Aborted.")
                return

        with transaction.atomic():
            for canonical, dupes in merges:
                dupe_pks = [d.pk for d in dupes]
                UserOrgParticipate.objects.filter(organization_id__in=dupe_pks).update(organization=canonical)
                Organization.objects.filter(pk__in=dupe_pks).delete()

        self.stdout.write(self.style.SUCCESS(f"Merged {total_dupes} duplicate organization(s)."))
