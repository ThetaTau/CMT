import datetime
import uuid

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate

# Freeze to noon UTC on a fixed mid-spring day so that ``datetime.date.today``
# (used to date the tasks) and django-filter's ``timezone.now()`` "today"
# option (UTC-based) always agree. TIME_ZONE is America/Phoenix (UTC-7), so
# without this a run during Phoenix evening lands on a different UTC calendar
# day and the ``?date=today`` filter matches nothing. Noon UTC = 05:00
# Phoenix, i.e. the same calendar date in both zones.
FROZEN_NOON_UTC = "2026-05-15 12:00:00"


def _make_officer(user, client):
    group, _ = Group.objects.get_or_create(name="officer")
    user.groups.add(group)
    client.force_login(user)


def _make_task_with_date(school_type="semester", days_offset=0, name=None):
    """Create a Task + TaskDate pair for view tests."""
    if name is None:
        name = f"View Test Task {school_type} {days_offset} {uuid.uuid4().hex[:8]}"
    task = Task(
        name=name,
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


def _other_chapter(than_chapter):
    """Return a Chapter guaranteed distinct from ``than_chapter``.

    ``ChapterFactory`` draws ``name`` from the small ``GREEK_ABR`` pool with
    ``django_get_or_create=("name",)`` and Faker is not seeded deterministically,
    so a bare ``ChapterFactory()`` intermittently returns the caller's own
    chapter and breaks "other chapter" assertions. Pick a different pool name
    explicitly so the returned row is always distinct.
    """
    from thetatauCMT.chapters.models import GREEK_ABR
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    other_name = next(name for name in GREEK_ABR.values() if name != than_chapter.name)
    return ChapterFactory(name=other_name)


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


# ---------------------------------------------------------------------------
# TaskListView complete/incomplete filtering
# ---------------------------------------------------------------------------
def _list_table_records(response):
    """Return the list of TaskDate records rendered by the main table."""
    table = response.context["table"]
    return [row.record for row in table.rows]


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_incomplete_excludes_tasks_completed_by_this_chapter(auto_login_user):
    """A TaskDate this chapter has completed must not appear under Incomplete."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, task_date = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    TaskChapter.objects.create(task=task_date, chapter=chapter, date=datetime.date.today())
    url = reverse("tasks:list")
    response = client.get(url, {"complete": "0", "date": "today"})
    assert task_date not in _list_table_records(response)


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_incomplete_includes_task_completed_only_by_other_chapter(auto_login_user):
    """A TaskDate completed by *another* chapter is still Incomplete for us."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, task_date = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    other_chapter = _other_chapter(chapter)
    TaskChapter.objects.create(task=task_date, chapter=other_chapter, date=datetime.date.today())
    url = reverse("tasks:list")
    response = client.get(url, {"complete": "0", "date": "today"})
    records = _list_table_records(response)
    assert task_date in records
    # And no duplicate rows for the same TaskDate.
    assert records.count(task_date) == 1


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_complete_shows_only_this_chapter_completions(auto_login_user):
    """Complete filter returns TaskDates this chapter has completed exactly once."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, ours = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    _, other_only = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    TaskChapter.objects.create(task=ours, chapter=chapter, date=datetime.date.today())
    TaskChapter.objects.create(task=other_only, chapter=_other_chapter(chapter), date=datetime.date.today())
    url = reverse("tasks:list")
    response = client.get(url, {"complete": "1", "date": "today"})
    records = _list_table_records(response)
    assert ours in records
    assert other_only not in records
    assert records.count(ours) == 1


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_all_filter_does_not_duplicate(auto_login_user):
    """Complete=All returns each TaskDate at most once even with multi-chapter completions."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, task_date = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    TaskChapter.objects.create(task=task_date, chapter=chapter, date=datetime.date.today())
    TaskChapter.objects.create(task=task_date, chapter=_other_chapter(chapter), date=datetime.date.today())
    url = reverse("tasks:list")
    response = client.get(url, {"complete": "A", "date": "today"})
    records = _list_table_records(response)
    assert records.count(task_date) == 1


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_complete_link_annotation_points_to_this_chapter(auto_login_user):
    """The complete_link annotation must be the current chapter's TaskChapter pk."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, task_date = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    ours = TaskChapter.objects.create(task=task_date, chapter=chapter, date=datetime.date.today())
    TaskChapter.objects.create(task=task_date, chapter=_other_chapter(chapter), date=datetime.date.today())
    url = reverse("tasks:list")
    response = client.get(url, {"complete": "1", "date": "today"})
    match = next(rec for rec in _list_table_records(response) if rec.pk == task_date.pk)
    assert match.complete_link == ours.pk


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_default_first_load_hides_completed_tasks(auto_login_user):
    """A bare `/tasks/` request should apply the Incomplete + current-term defaults."""
    from core.models import current_year_term_slug

    client, user = auto_login_user()
    chapter = user.current_chapter
    # A completed task dated today: current term includes today, so date passes;
    # but the default Incomplete filter must hide it.
    _, done = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    TaskChapter.objects.create(task=done, chapter=chapter, date=datetime.date.today())
    _, todo = _make_task_with_date(school_type=chapter.school_type, days_offset=0)

    url = reverse("tasks:list")
    response = client.get(url)  # no params → defaults kick in
    records = _list_table_records(response)
    assert done not in records
    assert todo in records
    # And the filter form remembers what was applied server-side.
    assert response.context["filter"].form.data.get("complete") == "0"
    assert response.context["filter"].form.data.get("date") == current_year_term_slug()


@pytest.mark.django_db
def test_task_list_cancel_clears_all_filters(auto_login_user):
    """The Clear button submits ?cancel=…; all filters (incl. defaults) drop."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, done = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    TaskChapter.objects.create(task=done, chapter=chapter, date=datetime.date.today())
    _, todo = _make_task_with_date(school_type=chapter.school_type, days_offset=0)

    url = reverse("tasks:list")
    response = client.get(url, {"cancel": "Clear"})
    records = _list_table_records(response)
    # With no filter at all, BOTH completed and incomplete tasks for the
    # chapter's school_type appear.
    assert done in records
    assert todo in records


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_task_owner_filter_narrows_results(auto_login_user):
    """The task__owner filter restricts rows to tasks with matching Task.owner."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, regent_task = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    # Second task with a *different* owner via a manual Task/TaskDate build.
    treasurer_task = Task(
        name=f"Treasurer Task {uuid.uuid4().hex[:8]}",
        owner="treasurer",
        type="task",
        resource="",
        description="Owner filter test",
    )
    treasurer_task.save()
    treasurer_task_date = TaskDate.objects.create(
        task=treasurer_task,
        school_type=chapter.school_type,
        date=datetime.date.today(),
    )

    url = reverse("tasks:list")
    response = client.get(url, {"complete": "A", "date": "today", "task__owner": "regent"})
    records = _list_table_records(response)
    assert regent_task in records
    assert treasurer_task_date not in records


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_complete_link_renders_in_html(auto_login_user):
    """The rendered HTML shows the 'Completed Task Information' link for the row."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, task_date = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    tc = TaskChapter.objects.create(task=task_date, chapter=chapter, date=datetime.date.today())

    url = reverse("tasks:list")
    response = client.get(url, {"complete": "1", "date": "today"})
    body = response.content.decode("utf-8")
    detail_url = reverse("tasks:detail", args=[tc.pk])
    assert "Completed Task Information" in body
    assert detail_url in body


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_incomplete_renders_none_placeholder_in_html(auto_login_user):
    """An incomplete row renders the '<i>None</i>' placeholder for complete_link."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, task_date = _make_task_with_date(school_type=chapter.school_type, days_offset=0)

    url = reverse("tasks:list")
    response = client.get(url, {"complete": "0", "date": "today"})
    body = response.content.decode("utf-8")
    assert task_date in _list_table_records(response)
    assert "<i>None</i>" in body


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_pagination_preserves_user_supplied_params(auto_login_user):
    """After filtering, the pagination link should keep the user's query params."""
    from urllib.parse import quote

    client, user = auto_login_user()
    chapter = user.current_chapter
    # Create enough incomplete rows to force a second page (per_page=40).
    for _ in range(45):
        _make_task_with_date(school_type=chapter.school_type, days_offset=0)

    url = reverse("tasks:list")
    response = client.get(url, {"complete": "0", "date": "today"})
    body = response.content.decode("utf-8")
    # bootstrap_pagination builds links using request.get_full_path(), so the
    # user-visible ?complete=0&date=today must round-trip.
    assert "complete=0" in body
    assert quote("date=today", safe="=") in body or "date=today" in body


# ---------------------------------------------------------------------------
# Archived ("no longer needed") TaskDates in the list + complete views
# ---------------------------------------------------------------------------
@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_hides_archived_by_default(auto_login_user):
    """An archived TaskDate must not appear in the list with default filters."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, archived = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    _, active = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    archived.archive(reason="Old")

    url = reverse("tasks:list")
    response = client.get(url, {"complete": "A", "date": "today"})
    records = _list_table_records(response)
    assert active in records
    assert archived not in records


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_shows_only_archived_with_filter(auto_login_user):
    """?archived=1 surfaces only archived rows."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, archived = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    _, active = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    archived.archive()

    url = reverse("tasks:list")
    response = client.get(url, {"complete": "A", "date": "today", "archived": "1"})
    records = _list_table_records(response)
    assert archived in records
    assert active not in records


@pytest.mark.django_db
@pytest.mark.freeze_time(FROZEN_NOON_UTC)
def test_task_list_shows_all_with_archived_all_filter(auto_login_user):
    """?archived=A returns both archived and active rows."""
    client, user = auto_login_user()
    chapter = user.current_chapter
    _, archived = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    _, active = _make_task_with_date(school_type=chapter.school_type, days_offset=0)
    archived.archive()

    url = reverse("tasks:list")
    response = client.get(url, {"complete": "A", "date": "today", "archived": "A"})
    records = _list_table_records(response)
    assert archived in records
    assert active in records


@pytest.mark.django_db
def test_task_complete_view_refuses_archived_date(auto_login_user):
    """Posting a completion for an archived date is rejected, no TaskChapter made."""
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    school_type = user.current_chapter.school_type
    _, task_date = _make_task_with_date(school_type=school_type, days_offset=10)
    task_date.archive(reason="Retired")

    url = reverse("tasks:complete", kwargs={"pk": task_date.pk})
    response = client.post(url, {})
    # form_invalid re-renders the page (200), and no completion is recorded.
    assert response.status_code == 200
    assert not TaskChapter.objects.filter(task=task_date, chapter=user.current_chapter).exists()


@pytest.mark.django_db
def test_task_complete_view_archived_context_flag(auto_login_user):
    """The complete page exposes is_archived so the template can warn officers."""
    client, user = auto_login_user(make_officer="regent")
    _make_officer(user, client)
    school_type = user.current_chapter.school_type
    _, task_date = _make_task_with_date(school_type=school_type, days_offset=10)
    task_date.archive()

    url = reverse("tasks:complete", kwargs={"pk": task_date.pk})
    response = client.get(url)
    assert response.status_code == 200
    assert response.context["is_archived"] is True
    assert "no longer needed" in response.content.decode("utf-8").lower()
