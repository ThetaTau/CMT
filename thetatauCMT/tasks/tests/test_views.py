import pytest
from django.urls import reverse
from django.contrib.auth.models import Group
from thetatauCMT.tasks.models import TaskDate, TaskChapter


def _make_officer(user, client):
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


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
    task_date = TaskDate.objects.first()
    if task_date is None:
        pytest.skip("No TaskDate in DB (tasks.json fixture not loaded)")
    url = reverse("tasks:complete", kwargs={"pk": task_date.pk})
    response = client.get(url)
    # OfficerRequiredMixin redirects non-officers to home
    assert response.status_code == 302


@pytest.mark.django_db
def test_task_detail_view_authenticated(auto_login_user):
    """TaskDetailView shows a specific TaskChapter completion record."""
    client, user = auto_login_user()
    task_date = TaskDate.objects.first()
    if task_date is None:
        pytest.skip("No TaskDate in DB")
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
