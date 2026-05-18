import datetime
import pytest
from django.utils import timezone
from django.utils.text import slugify
from thetatauCMT.tasks.models import Task, TaskDate, TaskChapter


# ---------------------------------------------------------------------------
# Task.__str__ and save
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_str():
    task = Task.objects.first()
    assert str(task) == task.name


@pytest.mark.django_db
def test_task_save_sets_slug():
    """Task.save() sets slug = slugify(name + owner)."""
    task = Task(
        name="My Custom Task",
        owner="regent",
        type="task",
        resource="",
        description="A task for testing slug generation",
    )
    task.save()
    assert task.slug == slugify("My Custom Task" + "regent")


# ---------------------------------------------------------------------------
# Task.render_task_link
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_render_task_link_http_resource():
    """A task with an http resource produces an <a> link."""
    task = Task(
        name="External Link Task",
        owner="regent",
        type="form",
        resource="https://example.com/form",
        description="A task linking to an external site",
    )
    task.save()
    link = task.render_task_link
    assert "href" in str(link)
    assert "https://example.com/form" in str(link)


@pytest.mark.django_db
def test_render_task_link_empty_resource():
    """A task with no resource returns empty string."""
    task = Task(
        name="No Resource Task",
        owner="regent",
        type="task",
        resource="",
        description="A task with no link",
    )
    task.save()
    link = task.render_task_link
    assert link == ""


# ---------------------------------------------------------------------------
# Task.all_dates_for_task_chapter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_all_dates_for_task_chapter_matches_school_type(chapter):
    """Only dates matching the chapter's school_type (or 'all') are returned."""
    task = Task.objects.first()
    dates = task.all_dates_for_task_chapter(chapter)
    # All returned dates should match chapter.school_type or be 'all'
    for td in dates:
        assert td.school_type in (chapter.school_type, "all")


# ---------------------------------------------------------------------------
# Task.incomplete_dates_for_task_chapter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_incomplete_dates_for_task_chapter_excludes_completed(chapter, task_chapter_factory):
    """Dates that have already been completed by the chapter are excluded."""
    task = Task.objects.first()
    # Mark one date as complete for the chapter
    task_date = task.dates.filter(
        school_type__in=[chapter.school_type, "all"]
    ).first()
    if task_date is None:
        pytest.skip("No task dates available for this chapter school_type")
    # Create a TaskChapter completion record
    TaskChapter.objects.create(
        task=task_date,
        chapter=chapter,
        date=timezone.now().date(),
    )
    incomplete = task.incomplete_dates_for_task_chapter(chapter)
    completed_ids = {task_date.pk}
    for td in incomplete:
        assert td.pk not in completed_ids


# ---------------------------------------------------------------------------
# TaskDate.__str__
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_date_str():
    task_date = TaskDate.objects.first()
    if task_date is None:
        pytest.skip("No TaskDate in DB")
    expected = f"{task_date.task.name} for {task_date.task.owner} due on {task_date.date}"
    assert str(task_date) == expected


# ---------------------------------------------------------------------------
# TaskDate.complete
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_date_complete_returns_empty_when_not_done(chapter):
    task_date = TaskDate.objects.filter(
        school_type__in=[chapter.school_type, "all"]
    ).first()
    if task_date is None:
        pytest.skip("No task dates available")
    completions = task_date.complete(chapter)
    # No TaskChapter exists, so result should be empty
    assert completions.count() == 0


# ---------------------------------------------------------------------------
# TaskDate.incomplete_dates_for_chapter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_incomplete_dates_for_chapter_returns_queryset(chapter):
    result = TaskDate.incomplete_dates_for_chapter(chapter)
    # Should be a queryset (may be empty), not None
    assert result is not None


@pytest.mark.django_db
def test_incomplete_dates_for_chapter_next_month_returns_queryset(chapter):
    result = TaskDate.incomplete_dates_for_chapter_next_month(chapter)
    assert result is not None


@pytest.mark.django_db
def test_dates_for_next_month_returns_queryset():
    result = TaskDate.dates_for_next_month()
    assert result is not None


# ---------------------------------------------------------------------------
# Task.completed_last
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_task_completed_last_returns_none_when_no_completions(chapter):
    task = Task.objects.first()
    result = task.completed_last(chapter)
    assert result is None
