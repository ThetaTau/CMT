"""iCal subscription feed tests (django-ical).

Acceptance criteria covered by name:
    * bad / unknown feed token returns 404
    * feed exposes only approved public + national events (pending/rejected/private excluded)
    * chapter-scoped feed includes only that chapter's public events
    * region-scoped feed includes only that region's chapters' public events
    * date window — events older than the past-weeks window are excluded, recent past + future kept
    * an event with a start time is a timed VEVENT, not an all-day one
    * to-dos appear as VTODO only when opted in and the member has a chapter
    * a member can create a feed from the calendar page form
    * quick-subscribe from a chapter page creates a chapter-scoped feed (idempotent)
    * a member can delete their own feed but not another member's feed
"""

import datetime
import uuid

import pytest
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.chapters.models import GREEK_ABR
from thetatauCMT.events.models import CalendarFeedSubscription
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.tasks.models import Task, TaskDate
from thetatauCMT.users.tests.factories import UserFactory

TODAY = timezone.localdate()
FUTURE = TODAY + datetime.timedelta(days=5)
RECENT_PAST = TODAY - datetime.timedelta(days=10)  # inside the 4-week window
OLD_PAST = TODAY - datetime.timedelta(days=60)  # outside the 4-week window
GREEK = list(GREEK_ABR.values())


def _evt_type():
    return ScoreType.objects.filter(type="Evt").first()


def _event(chapter, name, date=FUTURE, **kwargs):
    return EventFactory.create(chapter=chapter, type=_evt_type(), date=date, name=name, **kwargs)


def _national_event(name, date=FUTURE, **kwargs):
    return EventFactory.create(chapter=None, type=_evt_type(), date=date, name=name, is_national=True, **kwargs)


def _feed_content(client, feed):
    response = client.get(feed.get_feed_path())
    assert response.status_code == 200
    return response.content.decode()


# ===========================================================================
# Private token URLs
# ===========================================================================


@pytest.mark.django_db
def test_feed_bad_token_returns_404(client):
    """bad / unknown feed token returns 404"""
    url = reverse("events:ical", kwargs={"token": uuid.uuid4()})
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_feed_is_reachable_without_login(client, chapter_factory):
    """A calendar app fetches the token URL with no session — it must still work."""
    chapter = chapter_factory.create(name=GREEK[0])
    user = UserFactory.create(chapter=chapter, name="Anon Fetch Owner")
    feed = CalendarFeedSubscription.objects.create(user=user, name="Public Token")
    assert client.get(feed.get_feed_path()).status_code == 200


@pytest.mark.django_db
def test_national_feed_is_always_available(client, chapter_factory):
    """one national feed is always available (no login/setup) and holds only national events"""
    _national_event("Always National")
    _event(
        chapter_factory.create(name=GREEK[0]),
        "Chapter Public",
        is_public=True,
        approval_status="approved",
    )
    response = client.get(reverse("events:ical_national"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "BEGIN:VEVENT" in content
    assert "Always National" in content
    assert "Chapter Public" not in content  # national feed is national-only


@pytest.mark.django_db
def test_feed_emits_a_timed_event_for_a_start_time(client, chapter_factory):
    """an event with a start time is a timed VEVENT, not an all-day one"""
    chapter = chapter_factory.create(name=GREEK[0])
    user = UserFactory.create(chapter=chapter, name="Timed Feed Owner")
    _event(
        chapter,
        "Timed Gala",
        is_public=True,
        approval_status="approved",
        start_time=datetime.time(18, 30),
        time_zone="America/New_York",
        duration=2,
    )
    _event(chapter, "All Day Retreat", is_public=True, approval_status="approved", start_time=None)
    feed = CalendarFeedSubscription.objects.create(user=user, name="Timed")
    feed.chapters.add(chapter)

    content = _feed_content(client, feed)

    # A timed event carries the wall-clock start in the event's own zone.
    assert "DTSTART;TZID=America/New_York:" in content
    assert "T183000" in content
    assert "DTSTART;VALUE=DATE:" in content  # the all-day event is unchanged


# ===========================================================================
# Event scoping — only approved public + national
# ===========================================================================


@pytest.mark.django_db
def test_feed_includes_approved_public_and_national_excludes_the_rest(chapter_factory, client):
    """feed exposes only approved public + national events (pending/rejected/private excluded)"""
    ch_a, ch_b = chapter_factory.create(name=GREEK[0]), chapter_factory.create(name=GREEK[1])
    user = UserFactory.create(chapter=ch_a, name="Scope Owner")
    _event(ch_b, "Approved Public", is_public=True, approval_status="approved")
    _event(ch_b, "Pending Public", is_public=True, approval_status="pending")
    _event(ch_b, "Rejected Public", is_public=True, approval_status="rejected")
    _event(ch_b, "Private Event", is_public=False)
    _national_event("National Gala")
    feed = CalendarFeedSubscription.objects.create(user=user, name="Scope", include_national=True)
    feed.chapters.add(ch_b)

    content = _feed_content(client, feed)

    assert "BEGIN:VEVENT" in content
    assert "Approved Public" in content
    assert "National Gala" in content
    assert "Pending Public" not in content
    assert "Rejected Public" not in content
    assert "Private Event" not in content


@pytest.mark.django_db
def test_feed_chapter_scope_only_that_chapter(chapter_factory, client):
    """chapter-scoped feed includes only that chapter's public events"""
    ch_in, ch_out = chapter_factory.create(name=GREEK[0]), chapter_factory.create(name=GREEK[1])
    user = UserFactory.create(chapter=ch_in, name="Chapter Scope Owner")
    _event(ch_in, "Chosen Chapter Event", is_public=True, approval_status="approved")
    _event(ch_out, "Other Chapter Event", is_public=True, approval_status="approved")
    feed = CalendarFeedSubscription.objects.create(user=user, name="Ch", include_national=False)
    feed.chapters.add(ch_in)

    content = _feed_content(client, feed)

    assert "Chosen Chapter Event" in content
    assert "Other Chapter Event" not in content


@pytest.mark.django_db
def test_feed_region_scope_only_that_region(chapter_factory, region_factory, client):
    """region-scoped feed includes only that region's chapters' public events"""
    region_in = region_factory.create(name="Region In")
    region_out = region_factory.create(name="Region Out")
    ch_in = chapter_factory.create(name=GREEK[0], region=region_in)
    ch_out = chapter_factory.create(name=GREEK[1], region=region_out)
    user = UserFactory.create(chapter=ch_in, name="Region Scope Owner")
    _event(ch_in, "In Region Event", is_public=True, approval_status="approved")
    _event(ch_out, "Out Region Event", is_public=True, approval_status="approved")
    feed = CalendarFeedSubscription.objects.create(user=user, name="Rg", include_national=False)
    feed.regions.add(region_in)

    content = _feed_content(client, feed)

    assert "In Region Event" in content
    assert "Out Region Event" not in content


# ===========================================================================
# Date window
# ===========================================================================


@pytest.mark.django_db
def test_feed_excludes_events_older_than_window(chapter_factory, client):
    """date window — events older than the past-weeks window are excluded, recent past + future kept"""
    chapter = chapter_factory.create(name=GREEK[0])
    user = UserFactory.create(chapter=chapter, name="Window Owner")
    _event(chapter, "Recent Past Event", date=RECENT_PAST, is_public=True, approval_status="approved")
    _event(chapter, "Old Past Event", date=OLD_PAST, is_public=True, approval_status="approved")
    _event(chapter, "Future Event", date=FUTURE, is_public=True, approval_status="approved")
    feed = CalendarFeedSubscription.objects.create(user=user, name="Win", include_national=False)
    feed.chapters.add(chapter)

    content = _feed_content(client, feed)

    assert "Recent Past Event" in content
    assert "Future Event" in content
    assert "Old Past Event" not in content


# ===========================================================================
# To-dos (VTODO)
# ===========================================================================


@pytest.mark.django_db
def test_feed_includes_todos_as_vtodo_when_opted_in(chapter_factory, client):
    """to-dos appear as VTODO only when opted in and the member has a chapter"""
    chapter = chapter_factory.create(name=GREEK[0])
    user = UserFactory.create(chapter=chapter, name="Todo Owner")
    task = Task.objects.create(
        name="File Report",
        owner="regent",
        type="task",
        description="Submit the annual report",
        days_advance=90,
    )
    TaskDate.objects.create(task=task, school_type="all", date=FUTURE)
    feed = CalendarFeedSubscription.objects.create(user=user, name="Td", include_national=False, include_todos=True)

    content = _feed_content(client, feed)

    assert "BEGIN:VTODO" in content
    assert "To-do: File Report" in content


@pytest.mark.django_db
def test_feed_omits_todos_when_not_opted_in(chapter_factory, client):
    """A feed with include_todos off never emits VTODO items."""
    chapter = chapter_factory.create(name=GREEK[0])
    user = UserFactory.create(chapter=chapter, name="No Todo Owner")
    task = Task.objects.create(name="Hidden Task", owner="regent", type="task", description="x", days_advance=90)
    TaskDate.objects.create(task=task, school_type="all", date=FUTURE)
    feed = CalendarFeedSubscription.objects.create(user=user, name="NoTd", include_national=True, include_todos=False)

    content = _feed_content(client, feed)

    assert "BEGIN:VTODO" not in content
    assert "Hidden Task" not in content


@pytest.mark.django_db
def test_feed_todos_filtered_by_owner_role(chapter_factory, client):
    """to-do feeds can be limited to specific officer roles' tasks"""
    chapter = chapter_factory.create(name=GREEK[0])
    user = UserFactory.create(chapter=chapter, name="Role Filter Owner")
    regent_task = Task.objects.create(name="Regent Duty", owner="regent", type="task", description="x", days_advance=90)
    treasurer_task = Task.objects.create(
        name="Treasurer Duty", owner="treasurer", type="task", description="x", days_advance=90
    )
    TaskDate.objects.create(task=regent_task, school_type="all", date=FUTURE)
    TaskDate.objects.create(task=treasurer_task, school_type="all", date=FUTURE)
    feed = CalendarFeedSubscription.objects.create(
        user=user,
        name="Regent Only",
        include_national=False,
        include_todos=True,
        task_owner_roles=["regent"],
    )

    content = _feed_content(client, feed)

    assert "To-do: Regent Duty" in content
    assert "To-do: Treasurer Duty" not in content


@pytest.mark.django_db
def test_feed_todos_all_roles_when_empty(chapter_factory, client):
    """an empty role list includes every role's tasks"""
    chapter = chapter_factory.create(name=GREEK[0])
    user = UserFactory.create(chapter=chapter, name="All Roles Owner")
    for role, task_name in [("regent", "R Task"), ("treasurer", "T Task")]:
        task = Task.objects.create(name=task_name, owner=role, type="task", description="x", days_advance=90)
        TaskDate.objects.create(task=task, school_type="all", date=FUTURE)
    feed = CalendarFeedSubscription.objects.create(
        user=user,
        name="All Tasks",
        include_national=False,
        include_todos=True,
        task_owner_roles=[],
    )

    content = _feed_content(client, feed)

    assert "To-do: R Task" in content
    assert "To-do: T Task" in content


# ===========================================================================
# Subscription management UI
# ===========================================================================


@pytest.mark.django_db
def test_member_can_create_feed_from_form(auto_login_user, chapter_factory):
    """a member can create a feed from the feeds management page (prefixed 'new' form)"""
    chapter = chapter_factory.create(name=GREEK[0])
    client, user = auto_login_user()
    response = client.post(
        reverse("events:feeds"),
        data={"new-name": "My New Feed", "new-include_national": "on", "new-chapters": [chapter.pk]},
    )
    assert response.status_code == 302
    feed = CalendarFeedSubscription.objects.get(user=user, name="My New Feed")
    assert feed.include_national is True
    assert chapter in feed.chapters.all()


@pytest.mark.django_db
def test_feeds_page_lists_feeds_and_national_feed(auto_login_user):
    """The management page renders the always-available national feed + the member's feeds + create form."""
    client, user = auto_login_user()
    CalendarFeedSubscription.objects.create(user=user, name="Listed Feed")
    response = client.get(reverse("events:feeds"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "Listed Feed" in content
    assert "Create a new feed" in content
    # The always-available national feed is advertised on the page.
    assert "National Events" in content
    assert reverse("events:ical_national") in content
    # The to-do task reminders card + its create form are present.
    assert "Chapter To-do Reminders" in content
    assert reverse("events:feed_tasks") in content


@pytest.mark.django_db
def test_create_task_feed_from_card(auto_login_user):
    """the tasks card creates a to-dos-only feed limited to the chosen officer roles"""
    client, user = auto_login_user()
    response = client.post(
        reverse("events:feed_tasks"),
        data={"tasks-name": "Officer Tasks", "tasks-task_owner_roles": ["regent", "scribe"]},
    )
    assert response.status_code == 302
    feed = CalendarFeedSubscription.objects.get(user=user, name="Officer Tasks")
    assert feed.include_todos is True
    assert feed.include_national is False
    assert set(feed.task_owner_roles) == {"regent", "scribe"}


@pytest.mark.django_db
def test_edit_feed_adds_chapter(auto_login_user, chapter_factory):
    """editing an existing feed can add/remove chapters (option to grow one combined feed)"""
    client, user = auto_login_user()
    ch1 = chapter_factory.create(name=GREEK[0])
    ch2 = chapter_factory.create(name=GREEK[1])
    feed = CalendarFeedSubscription.objects.create(user=user, name="Combined")
    feed.chapters.add(ch1)
    prefix = f"feed{feed.pk}"

    response = client.post(
        reverse("events:feed_edit", kwargs={"pk": feed.pk}),
        data={
            f"{prefix}-name": "Combined",
            f"{prefix}-include_national": "on",
            f"{prefix}-chapters": [ch1.pk, ch2.pk],
        },
    )
    assert response.status_code == 302
    feed.refresh_from_db()
    assert set(feed.chapters.values_list("pk", flat=True)) == {ch1.pk, ch2.pk}


@pytest.mark.django_db
def test_edit_feed_is_user_scoped(auto_login_user):
    """a member cannot edit another member's feed"""
    client, _ = auto_login_user()
    other = UserFactory.create(name="Other Edit Owner")
    feed = CalendarFeedSubscription.objects.create(user=other, name="Theirs")
    prefix = f"feed{feed.pk}"
    response = client.post(
        reverse("events:feed_edit", kwargs={"pk": feed.pk}),
        data={f"{prefix}-name": "Hijacked"},
    )
    assert response.status_code == 404
    feed.refresh_from_db()
    assert feed.name == "Theirs"


@pytest.mark.django_db
def test_chapter_subscribe_creates_new_feed_when_none_exists(auto_login_user, chapter_factory):
    """subscribing from a chapter page with no existing feed creates one"""
    chapter = chapter_factory.create(name=GREEK[0])
    client, user = auto_login_user()

    response = client.post(
        reverse("events:feed_subscribe_chapter"),
        data={"chapter": chapter.slug, "feed": "new"},
    )
    assert response.status_code == 302
    feed = CalendarFeedSubscription.objects.get(user=user)
    assert chapter in feed.chapters.all()
    assert feed.include_national is False


@pytest.mark.django_db
def test_chapter_subscribe_adds_to_existing_feed(auto_login_user, chapter_factory):
    """subscribing from a chapter page adds to a chosen existing feed instead of making a new one"""
    ch1 = chapter_factory.create(name=GREEK[0])
    ch2 = chapter_factory.create(name=GREEK[1])
    client, user = auto_login_user()
    feed = CalendarFeedSubscription.objects.create(user=user, name="My Combined Feed")
    feed.chapters.add(ch1)

    response = client.post(
        reverse("events:feed_subscribe_chapter"),
        data={"chapter": ch2.slug, "feed": feed.pk},
    )
    assert response.status_code == 302
    # No new feed created — the chapter was added to the existing one.
    assert CalendarFeedSubscription.objects.filter(user=user).count() == 1
    feed.refresh_from_db()
    assert set(feed.chapters.values_list("pk", flat=True)) == {ch1.pk, ch2.pk}


@pytest.mark.django_db
def test_member_can_delete_own_feed(auto_login_user):
    """a member can delete their own feed"""
    client, user = auto_login_user()
    feed = CalendarFeedSubscription.objects.create(user=user, name="Mine")
    response = client.post(reverse("events:feed_delete", kwargs={"pk": feed.pk}))
    assert response.status_code == 302
    assert not CalendarFeedSubscription.objects.filter(pk=feed.pk).exists()


@pytest.mark.django_db
def test_member_cannot_delete_another_members_feed(auto_login_user):
    """a member cannot delete another member's feed"""
    client, _ = auto_login_user()
    other = UserFactory.create(name="Other Owner")
    feed = CalendarFeedSubscription.objects.create(user=other, name="Not Mine")
    response = client.post(reverse("events:feed_delete", kwargs={"pk": feed.pk}))
    assert response.status_code == 302
    assert CalendarFeedSubscription.objects.filter(pk=feed.pk).exists()


@pytest.mark.django_db
def test_region_autocomplete_returns_regions(auto_login_user, region_factory):
    """regions are a type-to-search multiselect backed by an autocomplete endpoint"""
    client, _ = auto_login_user()
    region_factory.create(name="Findable Region")
    response = client.get(reverse("events:region-feed-autocomplete"), {"q": "Findable"})
    assert response.status_code == 200
    assert "Findable Region" in response.content.decode()
