import pytest
from django.core.management import call_command
from django.urls import reverse

from thetatauCMT.chapters.models import ChapterCurricula
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.jobs.models import Major
from thetatauCMT.jobs.tests.test_models import _make_job


@pytest.fixture
def chapters(db):
    """Two chapters with no curricula, the factory seeds random ones."""
    pair = ChapterFactory(name="alpha"), ChapterFactory(name="beta")
    ChapterCurricula.objects.all().delete()
    return pair


@pytest.mark.django_db
def test_populate_job_majors_dedupes_across_chapters(chapters):
    first, second = chapters
    ChapterCurricula.objects.create(chapter=first, major="Mechanical Engineering", approved=True)
    ChapterCurricula.objects.create(chapter=second, major="  mechanical   engineering ", approved=True)
    ChapterCurricula.objects.create(chapter=second, major="Civil Engineering", approved=True)

    call_command("populate_job_majors", verbosity=0)

    assert sorted(Major.objects.values_list("name", flat=True)) == [
        "civil engineering",
        "mechanical engineering",
    ]


@pytest.mark.django_db
def test_populate_job_majors_skips_unapproved_curricula(chapters):
    first, _second = chapters
    ChapterCurricula.objects.create(chapter=first, major="Nuclear Engineering", approved=False)

    call_command("populate_job_majors", verbosity=0)
    assert not Major.objects.exists()

    call_command("populate_job_majors", "--include-unapproved", verbosity=0)
    assert list(Major.objects.values_list("name", flat=True)) == ["nuclear engineering"]


@pytest.mark.django_db
def test_populate_job_majors_is_idempotent(chapters):
    first, _second = chapters
    ChapterCurricula.objects.create(chapter=first, major="Computer Science", approved=True)

    call_command("populate_job_majors", verbosity=0)
    call_command("populate_job_majors", verbosity=0)

    assert Major.objects.count() == 1


@pytest.mark.django_db
def test_populate_job_majors_merges_existing_duplicates(chapters):
    keeper = Major.objects.create(name="Computer  Science ")
    duplicate = Major.objects.create(name="computer science")
    job = _make_job()
    job.majors.add(duplicate)

    call_command("populate_job_majors", verbosity=0)

    keeper.refresh_from_db()
    assert keeper.name == "computer science"
    assert not Major.objects.filter(pk=duplicate.pk).exists()
    assert list(job.majors.all()) == [keeper]


@pytest.mark.django_db
def test_populate_job_majors_matches_autocomplete_created_values(chapters, auto_login_user):
    """A major typed on the job form resolves to the imported row."""
    first, _second = chapters
    ChapterCurricula.objects.create(chapter=first, major="Computer Science", approved=True)
    call_command("populate_job_majors", verbosity=0)
    imported = Major.objects.get(name="computer science")

    client, _user = auto_login_user()
    response = client.post(reverse("jobs:major-autocomplete"), {"text": "Computer Science"})

    assert response.json()["id"] == str(imported.pk)
    assert Major.objects.count() == 1


@pytest.mark.django_db
def test_populate_job_majors_dry_run_writes_nothing(chapters):
    first, _second = chapters
    ChapterCurricula.objects.create(chapter=first, major="Computer Science", approved=True)
    ChapterCurricula.objects.create(chapter=first, major="Civil Engineering", approved=True)
    existing = Major.objects.create(name="Computer  SCIENCE")

    call_command("populate_job_majors", "--dry-run", verbosity=0)

    assert list(Major.objects.values_list("name", flat=True)) == [existing.name]
