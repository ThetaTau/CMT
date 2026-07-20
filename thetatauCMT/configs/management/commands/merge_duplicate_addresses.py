"""Merge duplicate `address.Address` rows.

Duplicates now happen because `get_or_create_address` (used by
`core.forms.ComponentAddressField`) never creates a new row when a matching
`(street_number, route, locality)` triple already exists, and picks the
oldest instead.  Historical data still has duplicates from before that rule
existed — this command sweeps them.
"""

from address.models import Address
from django.core.management.base import BaseCommand
from django.db.models import Count

from core.address import deduplicate


class Command(BaseCommand):
    help = "Merge duplicate Address rows, keeping the oldest and repointing FKs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report duplicates without modifying data.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        dup_keys = Address.objects.values("street_number", "route", "locality").annotate(n=Count("id")).filter(n__gt=1)
        total_groups = dup_keys.count()
        self.stdout.write(f"Found {total_groups} duplicate address group(s).")
        merged = 0
        for key in dup_keys:
            addresses = Address.objects.filter(
                street_number=key["street_number"],
                route=key["route"],
                locality_id=key["locality"],
            ).order_by("id")
            count = addresses.count()
            if count < 2:
                continue
            if dry_run:
                self.stdout.write(
                    f"  would merge {count} rows for "
                    f"{key['street_number']!r} {key['route']!r} locality={key['locality']}"
                )
                continue
            deduplicate(addresses)
            merged += count - 1
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes written."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Merged {merged} duplicate address row(s)."))
