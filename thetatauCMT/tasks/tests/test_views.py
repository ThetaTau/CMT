import datetime

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate


def _make_officer(user, client):
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


def _make_task_with_date(school_type="semester", days_offset=0):
    """Create a Task + TaskDate pair for view tests."""
    task = Task(
        name=f"View Test Task {school_type} {days_offset}",
        owner="regent",
        type="task",
        resource="",
        description="For view test",
    )
    task.save()
    due_date = datetime.date.today() + datetime.timedelta(days=days_offset)
    task_date = TaskDate.objects.create(
        task=task,
        school_type=school_type,
        date=due_date,
    )
    return task, task_date


@pytest.mark.django_db
def test_task_list_view_authenticated(auto_login_user):
    client, user = auto_login_user()
    url = reverse("tasks:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_task_list_view_unauthenticated(client):
    url = reverse("tasks:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_task_list_view_with_cancel_param(auto_login_user):
    """GET ?cancel=1 clears filter and still returns 200."""
    client, user = auto_login_user()
    url = reverse("tasks:list")
    response = client.get(url, {"cancel": "1"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_task_complete_view_officer_get_with_created_task(auto_login_user):
    """TaskCompleteView with a TaskDate created in this test — not DB-dependent."""
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    school_type = user.current_chapter.school_type
    _, task_date = _make_task_with_date(school_type=school_type, days_offset=10)
    url = reverse("tasks:complete", kwargs={"pk": task_date.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_task_complete_view_officer_get(auto_login_user):
    """TaskCompleteView requires officer role; GET shows the form."""
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    task_date = TaskDate.objects.first()
    if task_date is None:
        pytest.skip("No TaskDate in DB (tasks.json fixture not loaded)")
    url = reverse("tasks:complete", kwargs={"pk": task_date.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_task_complete_view_regular_user_redirected(auto_login_user):
    """Non-officer users are redirected from TaskCompleteView."""
    client, user = auto_login_user()
    _, task_date = _make_task_with_date(days_offset=5)
    url = reverse("tasks:complete", kwargs={"pk": task_date.pk})
    response = client.get(url)
    # OfficerRequiredMixin redirects non-officers to home
    assert response.status_code == 302


@pytest.mark.django_db
def test_task_detail_view_authenticated(auto_login_user):
    """TaskDetailView shows a specific TaskChapter completion record."""
    client, user = auto_login_user()
    _, task_date = _make_task_with_date(days_offset=5)
    chapter = user.current_chapter
    task_chapter = TaskChapter(
        task=task_date,
        chapter=chapter,
        date="2024-01-01",
    )
    task_chapter.save()
    url = reverse("tasks:detail", kwargs={"pk": task_chapter.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_task_detail_view_unauthenticated(client):
    url = reverse("tasks:detail", kwargs={"pk": 1})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
