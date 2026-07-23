"""Pre-fill the ``user_id`` column of a legacy award-winners CSV (read-only).

For every row that names an individual member, this runs the same confidence
matcher the award importer uses (exact id / email, then fuzzy full-name matching
raised by chapter + graduation-year agreement) and writes the matched member's
id into the ``user_id`` column -- but ONLY when the match is confident and
unambiguous. Uncertain rows are left blank ("skip unsure") for manual review, so
pre-filled ids can be trusted and the remaining blanks are the short list a human
still needs to resolve.

Read-only against the database: it only *looks up* members and never creates or
modifies any records, so it is safe to run against production. It writes solely
to the CSV file.

    # annotate in place (default)
    docker exec <prod_django> python manage.py match_award_user_ids \\
        /app/secrets/award_winners_import.csv

    # preview without writing, and list the rows it could not confidently match
    docker exec <prod_django> python manage.py match_award_user_ids \\
        /app/secrets/award_winners_import.csv --dry-run --show-unsure
"""

import csv
import io

from django.core.management import BaseCommand, CommandError

from thetatauCMT.awards.import_matching import match_member

USER_ID_FIELD = "user_id"
NAME_FIELD = "name"
CHAPTER_FIELD = "chapter"
GRAD_FIELD = "graduation_year"


class Command(BaseCommand):
    help = "Fill the user_id column of an award-winners CSV with confident member matches (read-only, prod-safe)."

    def add_arguments(self, parser):
        parser.add_argument("csv_path", help="Path to the award-winners CSV to annotate.")
        parser.add_argument(
            "--output",
            help="Where to write the annotated CSV (default: overwrite the input file in place).",
        )
        parser.add_argument(
            "--threshold",
            type=float,
            default=None,
            help="Auto-accept score threshold (default: settings.ATTENDANCE_MATCH_AUTO_ACCEPT_THRESHOLD, ~0.60).",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Re-match rows that already have a user_id (default: leave existing ids untouched).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing any file.",
        )
        parser.add_argument(
            "--show-unsure",
            action="store_true",
            help="List each named row left unmatched, with its best candidate and score.",
        )

    def handle(self, *args, **options):
        path = options["csv_path"]
        try:
            with open(path, newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                fieldnames = reader.fieldnames or []
                rows = list(reader)
        except OSError as exc:
            raise CommandError(f"Could not read CSV: {exc}")

        for required in (NAME_FIELD, USER_ID_FIELD):
            if required not in fieldnames:
                raise CommandError(f"CSV must have a '{required}' column; found headers: {fieldnames}")

        threshold = options["threshold"]
        overwrite = options["overwrite"]
        show_unsure = options["show_unsure"]
        filled = skipped_unsure = already = no_name = 0

        for row in rows:
            name = (row.get(NAME_FIELD) or "").strip()
            if not name:
                # Chapter / region awards carry no member name -> nothing to match.
                no_name += 1
                continue
            if (row.get(USER_ID_FIELD) or "").strip() and not overwrite:
                already += 1
                continue
            match = match_member(
                {
                    "name": name,
                    "chapter": (row.get(CHAPTER_FIELD) or "").strip(),
                    "graduation_year": (row.get(GRAD_FIELD) or "").strip(),
                },
                threshold=threshold,
            )
            if match.auto_accept and match.recipient is not None:
                row[USER_ID_FIELD] = str(match.recipient.pk)
                filled += 1
            else:
                skipped_unsure += 1
                if show_unsure:
                    best = match.candidates[0] if match.candidates else None
                    detail = (
                        f"best: {best['name']} [{best.get('chapter', '')}] score {best['score']:.2f}"
                        if best
                        else "no candidates found"
                    )
                    award = (row.get("award") or "").strip()
                    chapter = (row.get(CHAPTER_FIELD) or "").strip()
                    self.stdout.write(f"  UNSURE  [{award}] {name} / {chapter} -> {detail}")

        summary = (
            f"filled {filled}, skipped {skipped_unsure} unsure, "
            f"kept {already} already-set, {no_name} non-member (chapter/region) rows "
            f"of {len(rows)} total."
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"[dry-run] would fill user_id: {summary}"))
            return

        out_path = options.get("output") or path
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        try:
            with open(out_path, "w", newline="", encoding="utf-8") as handle:
                handle.write(buffer.getvalue())
        except OSError as exc:
            raise CommandError(f"Could not write CSV: {exc}")

        self.stdout.write(self.style.SUCCESS(f"Wrote {out_path}: {summary}"))
