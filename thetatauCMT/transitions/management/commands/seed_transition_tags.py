"""Seed TransitionTag rows for every region, active chapter, and a curated
general-purpose vocabulary (2026-09 follow-up to TRWI-13).

Unlike ``seed_transition_reports_demo`` this creates real production
vocabulary, not demo/QA fixtures -- it is intentionally NOT gated by
``core.seed_guard.ensure_seeding_allowed``, since running it against
production is the whole point. Idempotent and safe to re-run (e.g. on a
schedule, or after a new chapter/region is added) -- matching is
case-insensitive (``name__iexact``), mirroring
``TransitionTagAutocomplete.create_object``'s own dedup, so re-running only
ever adds names that are genuinely new.

    docker exec thetataucmt_local_django python manage.py seed_transition_tags [--dry-run]
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region
from thetatauCMT.transitions.models import TransitionTag

# General-purpose suggestions beyond the original TAG_CHOICES 9 (success,
# failure, contacts, expertise, calendar, systems, continuity, advice, risk
# -- see models.TAG_CHOICES/migration 0008). Chosen from themes that recur
# across real transition documents (budget lines, rush/tabling, ritual and
# initiation logistics, vendor relationships, chapter housing, alumni
# relations, event planning, committee structure) but weren't already
# covered by an existing tag.
SUGGESTED_TAG_NAMES = [
    "budget",
    "recruitment",
    "ritual",
    "vendor",
    "housing",
    "alumni",
    "events",
    "committees",
]


def _candidate_names():
    """Yield every name this command seeds: suggestions, then regions, then active chapters."""
    yield from SUGGESTED_TAG_NAMES
    yield from Region.objects.order_by("name").values_list("name", flat=True)
    yield from Chapter.objects.filter(active=True).order_by("name").values_list("name", flat=True)


class Command(BaseCommand):
    help = "Seed TransitionTag rows for every region, active chapter, and a curated general vocabulary."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        created = skipped = 0
        seen = set()

        with transaction.atomic():
            for raw_name in _candidate_names():
                name = " ".join((raw_name or "").split())
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())

                if TransitionTag.objects.filter(name__iexact=name).exists():
                    skipped += 1
                    continue
                created += 1
                if not dry_run:
                    TransitionTag.objects.create(name=name)

            if dry_run:
                transaction.set_rollback(True)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(f"{prefix}Tags: {created} created, {skipped} already existed.")
