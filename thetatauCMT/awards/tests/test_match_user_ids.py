import csv

import pytest
from django.core.management import call_command

from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HEADER = ["award", "cycle", "effective_date", "user_id", "name", "chapter", "graduation_year", "citation"]


def _write(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(rows)


def _read(path):
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def test_fills_confident_match_skips_unsure_and_chapter(tmp_path):
    user = UserFactory(name="Zebadiah Quillfeather")
    csv_path = tmp_path / "awards.csv"
    _write(
        csv_path,
        [
            ["Commendation", "2025", "", "", "Zebadiah Quillfeather", "", "", "citation, with comma"],
            ["Schrader Award", "2023-25", "", "", "", "Chi", "", ""],
            ["Commendation", "2025", "", "", "Nobody Matchington", "", "", ""],
        ],
    )
    call_command("match_award_user_ids", str(csv_path))
    rows = _read(csv_path)
    assert rows[0]["user_id"] == str(user.pk)  # confident member match -> filled
    assert rows[1]["user_id"] == ""  # chapter award (no name) -> untouched
    assert rows[2]["user_id"] == ""  # no such member -> skipped (unsure)
    # Unrelated columns (including a quoted citation) are preserved verbatim.
    assert rows[0]["citation"] == "citation, with comma"
    assert rows[1]["chapter"] == "Chi"


def test_existing_user_id_preserved_without_overwrite(tmp_path):
    UserFactory(name="Zebadiah Quillfeather")
    csv_path = tmp_path / "awards.csv"
    _write(csv_path, [["Commendation", "2025", "", "999999", "Zebadiah Quillfeather", "", "", ""]])
    call_command("match_award_user_ids", str(csv_path))
    assert _read(csv_path)[0]["user_id"] == "999999"  # left as-is without --overwrite


def test_overwrite_rematches_existing_user_id(tmp_path):
    user = UserFactory(name="Zebadiah Quillfeather")
    csv_path = tmp_path / "awards.csv"
    _write(csv_path, [["Commendation", "2025", "", "999999", "Zebadiah Quillfeather", "", "", ""]])
    call_command("match_award_user_ids", str(csv_path), overwrite=True)
    assert _read(csv_path)[0]["user_id"] == str(user.pk)


def test_dry_run_writes_nothing(tmp_path):
    UserFactory(name="Zebadiah Quillfeather")
    csv_path = tmp_path / "awards.csv"
    _write(csv_path, [["Commendation", "2025", "", "", "Zebadiah Quillfeather", "", "", ""]])
    before = csv_path.read_text(encoding="utf-8")
    call_command("match_award_user_ids", str(csv_path), dry_run=True)
    assert csv_path.read_text(encoding="utf-8") == before
