import datetime
from io import StringIO

import pytest
from django.core.management import call_command

from thetatauCMT.tasks.models import Task, TaskDate


def _make_task_with_date(school_type="semester", days_offset=0, name=None):
    task = Task(
        name=name or f"Cmd Task {school_type} {days_offset}",
        owner="regent",
        type="task",
        resource="",
        description="Command test",
    )
    task.save()
    due_date = datetime.date.today() + datetime.timedelta(days=days_offset)
    return task, TaskDate.objects.create(task=task, school_type=school_type, date=due_date)


@pytest.mark.django_db
def test_archive_old_task_dates_before(chapter):
    """--before archives only dates strictly before the cutoff."""
    school_type = chapter.school_type
    _, old = _make_task_with_date(school_type=school_type, days_offset=-400, name="Old Cmd")
    _, recent = _make_task_with_date(school_type=school_type, days_offset=5, name="Recent Cmd")
    cutoff = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()

    call_command("archive_old_task_dates", "--before", cutoff, stdout=StringIO())

    old.refresh_from_db()
    recent.refresh_from_db()
    assert old.archived is True
    assert old.archived_on is not None
    assert recent.archived is False


@pytest.mark.django_db
def test_archive_old_task_dates_older_than_days(chapter):
    """--older-than-days archives dates more than N days old."""
    school_type = chapter.school_type
    _, old = _make_task_with_date(school_type=school_type, days_offset=-200, name="Old2 Cmd")
    _, recent = _make_task_with_date(school_type=school_type, days_offset=-10, name="Recent2 Cmd")

    call_command("archive_old_task_dates", "--older-than-days", "180", stdout=StringIO())

    old.refresh_from_db()
    recent.refresh_from_db()
    assert old.archived is True
    assert recent.archived is False


@pytest.mark.django_db
def test_archive_old_task_dates_dry_run_changes_nothing(chapter):
    """--dry-run reports but does not modify any rows."""
    school_type = chapter.school_type
    _, old = _make_task_with_date(school_type=school_type, days_offset=-400, name="Dry Cmd")
    cutoff = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()
    out = StringIO()

    call_command("archive_old_task_dates", "--before", cutoff, "--dry-run", stdout=out)

    old.refresh_from_db()
    assert old.archived is False
    assert "Dry run" in out.getvalue()


@pytest.mark.django_db
def test_archive_old_task_dates_filter_by_task(chapter):
    """--task limits archiving to a single task name."""
    school_type = chapter.school_type
    _, target = _make_task_with_date(school_type=school_type, days_offset=-400, name="Target Cmd")
    _, other = _make_task_with_date(school_type=school_type, days_offset=-400, name="Other Cmd")
    cutoff = (datetime.date.today() - datetime.timedelta(days=100)).isoformat()

    call_command(
        "archive_old_task_dates",
        "--before",
        cutoff,
        "--task",
        "Target Cmd",
        stdout=StringIO(),
    )

    target.refresh_from_db()
    other.refresh_from_db()
    assert target.archived is True
    assert other.archived is False


@pytest.mark.django_db
def test_archive_old_task_dates_default_uses_academic_year(chapter):
    """With no cutoff arg, dates before the current academic year are archived."""
    from core.models import academic_encompass_start_end_date

    academic_start, _ = academic_encompass_start_end_date()
    school_type = chapter.school_type
    before_start = academic_start.date() - datetime.timedelta(days=5)
    after_start = academic_start.date() + datetime.timedelta(days=5)

    task_old = Task.objects.create(name="AY Old Cmd", owner="regent", type="task", resource="", description="x")
    old = TaskDate.objects.create(task=task_old, school_type=school_type, date=before_start)
    task_new = Task.objects.create(name="AY New Cmd", owner="regent", type="task", resource="", description="x")
    new = TaskDate.objects.create(task=task_new, school_type=school_type, date=after_start)

    call_command("archive_old_task_dates", stdout=StringIO())

    old.refresh_from_db()
    new.refresh_from_db()
    assert old.archived is True
    assert new.archived is False
