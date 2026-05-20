"""
Tests for thetatauCMT/regions/tables.py
Covers: get_value_from_a() helper and TaskLinkColumn.render()
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_get_value_from_a_empty_string_returns_false():
    """An empty string means the task is incomplete."""
    from thetatauCMT.regions.tables import get_value_from_a

    assert get_value_from_a("") is False


@pytest.mark.django_db
def test_get_value_from_a_na_returns_na():
    """'N/A' string means the task is not applicable."""
    from thetatauCMT.regions.tables import get_value_from_a

    assert get_value_from_a("N/A") == "N/A"


@pytest.mark.django_db
def test_get_value_from_a_completed_task_info_returns_true():
    """A value containing 'Completed Task Information' means complete."""
    from thetatauCMT.regions.tables import get_value_from_a

    assert get_value_from_a("Completed Task Information for Audit") is True


@pytest.mark.django_db
def test_get_value_from_a_other_value_returns_empty_string():
    """Any other value means it's not a task column."""
    from thetatauCMT.regions.tables import get_value_from_a

    assert get_value_from_a("Some other value") == ""


@pytest.mark.django_db
def test_task_link_column_render_none_returns_na():
    """render(None) should return the string 'N/A'."""
    from thetatauCMT.regions.tables import TaskLinkColumn

    col = TaskLinkColumn()
    assert col.render(None) == "N/A"


@pytest.mark.django_db
def test_task_link_column_render_zero_returns_empty():
    """render(0) should return empty string (no task chapter)."""
    from thetatauCMT.regions.tables import TaskLinkColumn

    col = TaskLinkColumn()
    assert col.render(0) == ""


@pytest.mark.django_db
def test_task_link_column_render_valid_pk_returns_link():
    """render(pk) should return an anchor tag pointing to tasks:detail."""
    from thetatauCMT.regions.tables import TaskLinkColumn

    col = TaskLinkColumn()
    result = col.render(42)
    expected_url = reverse("tasks:detail", args=[42])
    assert expected_url in result
    assert "Completed Task Information" in result
    assert 'target="_blank"' in result
