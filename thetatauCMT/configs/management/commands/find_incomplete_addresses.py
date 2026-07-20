"""Find (and optionally repair) `address.Address` rows that are missing both
``street_number`` and ``route``.

These typically come from two sources:

* The old Google Places widget accepted a raw text but never got a
  ``street_number``/``route`` back from the geocoder — so the address was
  saved with the full text in ``raw`` but no split components.
* The user only ever supplied a city/state/zip (no street).

In the first case the street is usually still recoverable from ``raw`` (the
first comma-separated segment, if it starts with a digit).  In the second
case the data was never captured to begin with — nothing to recover.

Default behaviour is a diagnostic report.  Pass ``--csv PATH`` to dump the
full list for offline inspection, and ``--repair`` to write the parsed
street back into the row (safe: only touches rows where the first raw
segment starts with a digit and differs from the locality name).
"""

import csv
import re

from address.models import Address
from django.core.management.base import BaseCommand

from core.address import split_street


class Command(BaseCommand):
    help = (
        "Report Address rows that are missing street_number and route. "
        "Optionally dump to CSV and/or repair rows whose `raw` field still "
        "contains a parseable street."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            dest="csv_path",
            help="Write the full list of incomplete addresses to this CSV file.",
        )
        parser.add_argument(
            "--repair",
            action="store_true",
            help="For rows where `raw` starts with a street-like segment, split it "
            "into street_number/route and save. Rows that look empty or match the "
            "locality are left alone.",
        )
        parser.add_argument(
            "--samples",
            type=int,
            default=20,
            help="Number of sample rows to print per category (default: 20).",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_path"]
        repair = options["repair"]
        samples = options["samples"]

        qs = Address.objects.filter(street_number="", route="").select_related("locality__state__country")
        total = qs.count()
        self.stdout.write(f"Found {total} address(es) missing street_number and route.")
        if total == 0:
            return

        recoverable = []
        locality_only = []
        empty_raw = []

        for addr in qs.iterator():
            raw = (addr.raw or "").strip()
            locality_name = addr.locality.name if addr.locality else ""
            if not raw:
                empty_raw.append(addr)
                continue
            first = raw.split(",", 1)[0].strip()
            if not first or (locality_name and first.lower() == locality_name.lower()):
                locality_only.append(addr)
                continue
            # Street segment must start with a digit or look like a named property
            # (avoid mis-classifying "Springfield, IL 62701" as a street).
            if _looks_like_street(first):
                recoverable.append((addr, first))
            else:
                locality_only.append(addr)

        self.stdout.write("")
        self.stdout.write(f"  {len(recoverable):>5}  Recoverable (raw starts with a street-like segment)")
        self.stdout.write(f"  {len(locality_only):>5}  Locality-only (raw appears to hold no street)")
        self.stdout.write(f"  {len(empty_raw):>5}  Empty raw (no data to recover)")
        self.stdout.write("")

        def _linked(addr):
            users = list(addr.user_set.values_list("name", flat=True)[:5])
            chapters = list(addr.chapter_set.values_list("name", flat=True)[:5])
            return users, chapters

        self.stdout.write(self.style.MIGRATE_HEADING("Recoverable samples:"))
        for addr, first in recoverable[:samples]:
            u, c = _linked(addr)
            self.stdout.write(f"  #{addr.pk}  raw={addr.raw!r}  street->{first!r}  users={u}  chapters={c}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Locality-only samples:"))
        for addr in locality_only[:samples]:
            u, c = _linked(addr)
            self.stdout.write(f"  #{addr.pk}  raw={addr.raw!r}  locality={addr.locality}  users={u}  chapters={c}")

        if csv_path:
            self._write_csv(csv_path, recoverable, locality_only, empty_raw)
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"Wrote full list to {csv_path}"))

        if repair:
            self._repair(recoverable)

    def _write_csv(self, path, recoverable, locality_only, empty_raw):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                [
                    "category",
                    "address_id",
                    "raw",
                    "formatted",
                    "locality",
                    "state",
                    "postal_code",
                    "country",
                    "suggested_street",
                    "linked_users",
                    "linked_chapters",
                ]
            )
            for category, items in (
                ("recoverable", [(a, first) for a, first in recoverable]),
                ("locality_only", [(a, "") for a in locality_only]),
                ("empty_raw", [(a, "") for a in empty_raw]),
            ):
                for addr, suggested in items:
                    loc = addr.locality
                    state = loc.state if loc else None
                    country = state.country if state else None
                    users = ", ".join(addr.user_set.values_list("name", flat=True))
                    chapters = ", ".join(addr.chapter_set.values_list("name", flat=True))
                    w.writerow(
                        [
                            category,
                            addr.pk,
                            addr.raw or "",
                            addr.formatted or "",
                            loc.name if loc else "",
                            state.name if state else "",
                            loc.postal_code if loc else "",
                            country.name if country else "",
                            suggested,
                            users,
                            chapters,
                        ]
                    )

    def _repair(self, recoverable):
        repaired = 0
        for addr, first in recoverable:
            street_number, route = split_street(first)
            if not route and not street_number:
                continue
            addr.street_number = street_number
            addr.route = route
            if not addr.formatted:
                addr.formatted = str(addr)
            addr.save(update_fields=["street_number", "route", "formatted"])
            repaired += 1
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Repaired {repaired} address row(s)."))


_STREET_LEAD = re.compile(r"^\s*(?:\d+|[A-Za-z]+\s+\d)")


def _looks_like_street(segment):
    """Return True when a comma-segment plausibly represents a street rather
    than a city/region. Requires either a leading number ("123 Main St") or a
    named-property pattern ("Suite 400", "Building 12")."""
    if not segment:
        return False
    return bool(_STREET_LEAD.match(segment))
