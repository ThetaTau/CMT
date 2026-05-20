"""
Unit tests for thetatauCMT/tasks/tables.py.

Covers:
- TaskTable instantiation with complete=True (default)
- render_form method called on a record
- render_complete_link with a non-zero value (renders link)
- render_complete_link with value==0 (renders 'None')
"""

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# TaskTable instantiation
# ---------------------------------------------------------------------------


def test_task_table_instantiates_with_complete_true():
    """TaskTable can be instantiated with complete=True (default)."""
    from thetatauCMT.tasks.tables import TaskTable

    table = TaskTable(data=[], complete=True)
    # The extra 'complete_link' column should be present
    assert "complete_link" in table.columns.names()


def test_task_table_instantiates_with_complete_false():
    """TaskTable omits complete_link column when complete=False."""
    from thetatauCMT.tasks.tables import TaskTable

    table = TaskTable(data=[], complete=False)
    assert "complete_link" not in table.columns.names()


# ---------------------------------------------------------------------------
# render_form
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_render_form_returns_task_link():
    """render_form returns the task's render_task_link value."""
    from thetatauCMT.tasks.models import Task
    from thetatauCMT.tasks.tables import TaskTable

    # Build a minimal Task
    task = Task(
        name="render_form test task",
        owner="regent",
        type="task",
        resource="http://example.com",
        description="Table render test",
    )
    task.save()

    # Build a mock record with a .task attribute pointing to the task
    record = MagicMock()
    record.task = task

    table = TaskTable(data=[], complete=False)
    result = table.render_form(record)
    # render_task_link for an http resource returns a safe string with an <a> tag
    assert "href" in str(result)


# ---------------------------------------------------------------------------
# render_complete_link
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_render_complete_link_with_nonzero_value():
    """render_complete_link with a TaskChapter pk creates a link to tasks:detail."""
    import datetime

    from django.utils import timezone  # noqa: F401

    from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate
    from thetatauCMT.tasks.tables import TaskTable

    # Create a real TaskChapter so the reverse URL resolves
    task = Task(
        name="complete link test",
        owner="regent",
        type="task",
        resource="",
        description="Complete link test",
    )
    task.save()
    task_date = TaskDate.objects.create(
        task=task,
        school_type="semester",
        date=datetime.date.today() + datetime.timedelta(days=10),
    )
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    chapter = ChapterFactory()
    tc = TaskChapter.objects.create(task=task_date, chapter=chapter, date=datetime.date.today())

    table = TaskTable(data=[], complete=True)
    result = table.render_complete_link(tc.pk)
    result_str = str(result)
    assert "Completed Task Information" in result_str
    assert "href" in result_str


@pytest.mark.django_db
def test_render_complete_link_with_zero_value():
    """render_complete_link with value 0 renders the 'None' placeholder."""
    from thetatauCMT.tasks.tables import TaskTable

    table = TaskTable(data=[], complete=True)
    result = table.render_complete_link(0)
    assert "None" in str(result)
