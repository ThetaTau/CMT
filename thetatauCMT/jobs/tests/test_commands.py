import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from thetatauCMT.jobs.management.commands.populate_job_majors import DEFAULT_PATH, normalize
from thetatauCMT.jobs.models import Major
from thetatauCMT.jobs.tests.test_models import _make_job


@pytest.fixture
def fixture_entries():
    return json.loads(DEFAULT_PATH.read_text(encoding="utf-8"))


def test_fixture_has_no_repeated_spelling(fixture_entries):
    """Every canonical name and alias appears exactly once across the file."""
    seen = {}
    for entry in fixture_entries:
        canonical = normalize(entry["name"])
        assert canonical == entry["name"], f"{entry['name']!r} is not normalized"
        for spelling in [canonical] + [normalize(alias) for alias in entry.get("aliases", [])]:
            assert spelling not in seen, f"{spelling!r} maps to {seen.get(spelling)!r} and {canonical!r}"
            seen[spelling] = canonical


@pytest.mark.django_db
def test_populate_job_majors_creates_every_canonical(fixture_entries):
    call_command("populate_job_majors", verbosity=0)

    assert Major.objects.count() == len(fixture_entries)
    assert Major.objects.filter(name="mechanical engineering").exists()
    assert not Major.objects.filter(name="mechanical engineeering").exists()


@pytest.mark.django_db
def test_populate_job_majors_merges_alias_rows():
    """A lone alias row is renamed in place, so its job tags survive."""
    alias = Major.objects.create(name="Aerospace Engiineering")
    job = _make_job()
    job.majors.add(alias)

    call_command("populate_job_majors", verbosity=0)

    alias.refresh_from_db()
    assert alias.name == "aerospace engineering"
    assert list(job.majors.all()) == [alias]


@pytest.mark.django_db
def test_populate_job_majors_keeps_row_already_named_correctly():
    """When both spellings exist the canonical row wins and the alias is removed."""
    keeper = Major.objects.create(name="civil engineering")
    alias = Major.objects.create(name="civil and structural engineering")
    job = _make_job()
    job.majors.add(keeper)
    job.majors.add(alias)

    call_command("populate_job_majors", verbosity=0)

    keeper.refresh_from_db()
    assert keeper.name == "civil engineering"
    assert not Major.objects.filter(pk=alias.pk).exists()
    assert list(job.majors.all()) == [keeper]


@pytest.mark.django_db
def test_populate_job_majors_lowercases_existing(fixture_entries):
    major = Major.objects.create(name="Computer  SCIENCE ")

    call_command("populate_job_majors", verbosity=0)

    major.refresh_from_db()
    assert major.name == "computer science"
    assert Major.objects.count() == len(fixture_entries)


@pytest.mark.django_db
def test_populate_job_majors_keeps_majors_not_in_fixture(fixture_entries):
    unknown = Major.objects.create(name="underwater basket weaving")

    call_command("populate_job_majors", verbosity=0)

    unknown.refresh_from_db()
    assert unknown.name == "underwater basket weaving"
    assert Major.objects.count() == len(fixture_entries) + 1


@pytest.mark.django_db
def test_populate_job_majors_is_idempotent(fixture_entries):
    call_command("populate_job_majors", verbosity=0)
    call_command("populate_job_majors", verbosity=0)

    assert Major.objects.count() == len(fixture_entries)


@pytest.mark.django_db
def test_populate_job_majors_dry_run_writes_nothing():
    existing = Major.objects.create(name="Mechanical Engineeering")

    call_command("populate_job_majors", "--dry-run", verbosity=0)

    assert list(Major.objects.values_list("name", flat=True)) == [existing.name]


@pytest.mark.django_db
def test_populate_job_majors_rejects_conflicting_fixture(tmp_path):
    path = tmp_path / "job_majors.json"
    path.write_text(
        json.dumps(
            [
                {"name": "computer science", "aliases": ["computing"]},
                {"name": "software engineering", "aliases": ["Computing"]},
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="computing"):
        call_command("populate_job_majors", "--path", str(path), verbosity=0)

    assert not Major.objects.exists()


@pytest.mark.django_db
def test_populate_job_majors_matches_autocomplete_created_values(auto_login_user):
    """A major typed on the job form resolves to the curated row."""
    call_command("populate_job_majors", verbosity=0)
    curated = Major.objects.get(name="computer science")

    client, _user = auto_login_user()
    response = client.post(reverse("jobs:major-autocomplete"), {"text": "Computer Science"})

    assert response.json()["id"] == str(curated.pk)
    assert not Major.objects.filter(name="Computer Science").exists()
