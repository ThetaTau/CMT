"""Tests for the chapter activity feed collector and view.

Runs against the podman container's test DB (invoked via `podman exec
thetataucmt_local_django pytest ...`). Do not run against the host venv.
"""

import datetime

import pytest
from django.contrib.auth.models import Group
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.chapters.activity import (
    CATEGORIES,
    CATEGORY_EVENT,
    CATEGORY_SUBMISSION,
    CATEGORY_TASK,
    iter_chapter_activity,
)
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.submissions.tests.factories import SubmissionFactory
from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate


def _add_to_group(user, group_name):
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def _make_task_chapter(chapter, when):
    task, _ = Task.objects.get_or_create(
        slug=f"activity-test-task-{chapter.pk}",
        defaults={
            "name": "Activity Test Task",
            "owner": "regent",
            "type": "task",
            "description": "unit test task",
        },
    )
    task_date, _ = TaskDate.objects.get_or_create(
        task=task,
        school_type="all",
        date=when,
    )
    return TaskChapter.objects.create(task=task_date, chapter=chapter, date=when)


# ─── iter_chapter_activity() ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_iter_chapter_activity_returns_events_and_submissions_in_window():
    chapter = ChapterFactory()
    today = timezone.now().date()
    inside = today - datetime.timedelta(days=10)
    outside = today - datetime.timedelta(days=365)

    inside_event = EventFactory(chapter=chapter, date=inside)
    EventFactory(chapter=chapter, date=outside)
    inside_sub = SubmissionFactory(chapter=chapter, date=inside)
    SubmissionFactory(chapter=chapter, date=outside)

    other_chapter = ChapterFactory()
    EventFactory(chapter=other_chapter, date=inside)

    start = timezone.now() - datetime.timedelta(days=90)
    end = timezone.now() + datetime.timedelta(days=1)
    items = iter_chapter_activity(chapter, start, end)

    categories = {i.category for i in items}
    assert CATEGORY_EVENT in categories
    assert CATEGORY_SUBMISSION in categories

    titles = {i.title for i in items}
    assert inside_event.name in titles
    assert inside_sub.name in titles

    # Nothing from the other chapter and nothing outside the window
    for i in items:
        assert i.title != "" or i.category  # sanity
    # Only one event and one submission for this chapter fall inside the window
    assert sum(1 for i in items if i.category == CATEGORY_EVENT) == 1
    assert sum(1 for i in items if i.category == CATEGORY_SUBMISSION) == 1


@pytest.mark.django_db
def test_iter_chapter_activity_includes_task_completions():
    chapter = ChapterFactory()
    inside = timezone.now().date() - datetime.timedelta(days=5)
    tc = _make_task_chapter(chapter, inside)

    start = timezone.now() - datetime.timedelta(days=30)
    end = timezone.now() + datetime.timedelta(days=1)
    items = iter_chapter_activity(chapter, start, end)

    task_items = [i for i in items if i.category == CATEGORY_TASK]
    assert len(task_items) == 1
    assert task_items[0].title == tc.task.task.name
    assert task_items[0].url  # link resolved


@pytest.mark.django_db
def test_iter_chapter_activity_sorted_newest_first():
    chapter = ChapterFactory()
    today = timezone.now().date()
    old = EventFactory(chapter=chapter, date=today - datetime.timedelta(days=20))
    new = EventFactory(chapter=chapter, date=today - datetime.timedelta(days=2))

    start = timezone.now() - datetime.timedelta(days=90)
    end = timezone.now() + datetime.timedelta(days=1)
    items = iter_chapter_activity(chapter, start, end)

    event_titles = [i.title for i in items if i.category == CATEGORY_EVENT]
    assert event_titles.index(new.name) < event_titles.index(old.name)


# ─── ChapterActivityView permissions ──────────────────────────────────────────


@pytest.mark.django_db
def test_activity_view_forbidden_to_regular_member(auto_login_user):
    chapter = ChapterFactory()
    client, user = auto_login_user()
    url = reverse("chapters:activity", kwargs={"slug": chapter.slug})
    response = client.get(url, follow=True)
    # Non-officer, non-superuser, non-natoff -> redirected to home
    assert response.status_code == 200
    assert response.request["PATH_INFO"] != url


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_activity_view_allowed_for_superuser(auto_login_user, user_factory):
    chapter = ChapterFactory()
    user = user_factory.create(chapter=chapter)
    user.is_superuser = True
    user.save()
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert "All Chapter Activity" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_activity_view_allowed_for_natoff(auto_login_user, user_factory):
    other_chapter = ChapterFactory()
    user = user_factory.create()
    _add_to_group(user, "natoff")
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": other_chapter.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_activity_view_allowed_for_own_chapter_officer(auto_login_user, user_factory):
    chapter = ChapterFactory()
    user = user_factory.create(chapter=chapter)
    _add_to_group(user, "officer")
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_activity_view_denied_for_officer_of_different_chapter(auto_login_user, user_factory):
    my_chapter = ChapterFactory()
    other_chapter = ChapterFactory()
    user = user_factory.create(chapter=my_chapter)
    _add_to_group(user, "officer")
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": other_chapter.slug})
    response = client.get(url, follow=True)
    # Redirect to home; final URL is not the requested activity URL
    assert response.status_code == 200
    assert response.request["PATH_INFO"] != url


# ─── ChapterActivityView context ──────────────────────────────────────────────


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_activity_view_renders_recent_event(auto_login_user, user_factory):
    chapter = ChapterFactory()
    today = timezone.now().date()
    event = EventFactory(chapter=chapter, date=today - datetime.timedelta(days=5))

    user = user_factory.create(chapter=chapter)
    user.is_superuser = True
    user.save()
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": chapter.slug})
    response = client.get(url + "?window=6m")
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert event.name in body
    assert "All Chapter Activity" in body


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_activity_view_category_filter(auto_login_user, user_factory):
    chapter = ChapterFactory()
    today = timezone.now().date()
    inside = today - datetime.timedelta(days=3)
    event = EventFactory(chapter=chapter, date=inside)
    sub = SubmissionFactory(chapter=chapter, date=inside)

    user = user_factory.create(chapter=chapter)
    user.is_superuser = True
    user.save()
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": chapter.slug})

    response = client.get(url + "?window=6m&category=Event")
    assert response.status_code == 200
    ctx_items = response.context["activity_items"]
    categories = {i.category for i in ctx_items}
    assert categories == {"Event"}
    titles = {i.title for i in ctx_items}
    assert event.name in titles
    assert sub.name not in titles


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_activity_view_window_defaults_to_six_months(auto_login_user, user_factory):
    chapter = ChapterFactory()
    user = user_factory.create(chapter=chapter)
    user.is_superuser = True
    user.save()
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["selected_window"] == "6m"
    span = (response.context["end_date"] - response.context["start_date"]).days
    # 6 months ≈ 180 days (± a couple for month lengths)
    assert 170 <= span <= 195


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_activity_view_provides_all_category_counts(auto_login_user, user_factory):
    chapter = ChapterFactory()
    user = user_factory.create(chapter=chapter)
    user.is_superuser = True
    user.save()
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": chapter.slug})
    response = client.get(url)
    assert response.status_code == 200
    counts = response.context["counts"]
    for cat in CATEGORIES:
        assert cat in counts


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_activity_view_paginates_when_over_page_size(auto_login_user, user_factory):
    from thetatauCMT.chapters.views import ChapterActivityView

    per_page = ChapterActivityView.per_page
    chapter = ChapterFactory()
    today = timezone.now().date()
    # Create per_page + 5 events inside the window; unique dates to avoid the
    # (name, date, chapter) unique_together.
    for i in range(per_page + 5):
        EventFactory(chapter=chapter, date=today - datetime.timedelta(days=i))

    user = user_factory.create(chapter=chapter)
    user.is_superuser = True
    user.save()
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity", kwargs={"slug": chapter.slug})

    response = client.get(url + "?window=12m")
    assert response.status_code == 200
    paginator = response.context["paginator"]
    assert paginator.count >= per_page + 5
    assert response.context["is_paginated"] is True
    assert paginator.num_pages >= 2
    assert len(response.context["activity_items"]) == per_page
    assert response.context["page_obj"].number == 1

    response2 = client.get(url + "?window=12m&page=2")
    assert response2.status_code == 200
    assert response2.context["page_obj"].number == 2
    expected_last_page = paginator.count - per_page * (paginator.num_pages - 1)
    if paginator.num_pages == 2:
        assert len(response2.context["activity_items"]) == expected_last_page
    else:
        assert len(response2.context["activity_items"]) == per_page

    # Out-of-range page falls back to the last page
    response3 = client.get(url + "?window=12m&page=999")
    assert response3.status_code == 200
    assert response3.context["page_obj"].number == paginator.num_pages

    # Non-integer page falls back to the first page
    response4 = client.get(url + "?window=12m&page=abc")
    assert response4.status_code == 200
    assert response4.context["page_obj"].number == 1


# ─── activity_redirect ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_activity_redirect_sends_officer_to_own_chapter(auto_login_user, user_factory):
    chapter = ChapterFactory()
    user = user_factory.create(chapter=chapter)
    _add_to_group(user, "officer")
    client, _ = auto_login_user(user=user)
    url = reverse("chapters:activity_redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("chapters:activity", kwargs={"slug": chapter.slug})
