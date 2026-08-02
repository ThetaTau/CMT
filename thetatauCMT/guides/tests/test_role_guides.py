"""Role Guides (TWI-12).

The guide answers "what am I responsible for?", and it answers it from live data
-- the same ``TaskDate`` rows the home page and ``/tasks/`` use -- rather than
from a second hand-written checklist that would immediately drift. These tests
are mostly about that join staying honest: the right role, the right chapter,
and nothing the viewer would be bounced off if they clicked it.
"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.guides import services
from thetatauCMT.guides.models import Audience, FeatureArea, RoleGuide
from thetatauCMT.guides.tests.factories import FeatureFactory, RoleGuideFactory, RoleGuideStepFactory
from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _empty_registry(db, request):
    """Start each test from an empty registry.

    A reused test database may already hold the real registry, and
    ``RoleGuideFactory`` matches on ``role`` -- so ``RoleGuideFactory(role="treasurer")``
    would silently hand back the shipped Treasurer guide and its sixty steps.
    Skipped for the one test that asks for the real thing.
    """
    if "feature_registry" in request.fixturenames:
        return
    FeatureArea.objects.all().delete()
    RoleGuide.objects.all().delete()


def _in_group(user, name):
    user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def _member():
    return UserFactory(status="active")


def _officer(*roles):
    user = _in_group(_member(), "officer")
    user.current_roles = list(roles) or ["treasurer"]
    user.save(update_fields=["current_roles"])
    return user


def _natoff(*roles):
    user = _in_group(_member(), "natoff")
    user.current_roles = list(roles) or ["regional director"]
    user.save(update_fields=["current_roles"])
    return user


def _task(owner, name, chapter, days=10, archived=False):
    """A task with one upcoming due date this chapter can see."""
    task = Task.objects.create(name=name, owner=owner, type="task", description=name)
    TaskDate.objects.create(
        task=task,
        school_type=chapter.school_type,
        date=timezone.now().date() + timedelta(days=days),
        archived=archived,
    )
    return task


# ---------------------------------------------------------------------------
# get_role_guides -- which guides are "mine"
# ---------------------------------------------------------------------------
def test_a_member_with_no_office_gets_no_guides():
    """Not every guide -- the index page is what lists them all."""
    RoleGuideFactory(role="treasurer")
    assert services.get_role_guides(_member()) == []


def test_an_officer_gets_their_own_guide():
    treasurer = RoleGuideFactory(role="treasurer")
    RoleGuideFactory(role="scribe")
    assert services.get_role_guides(_officer("treasurer")) == [treasurer]


def test_two_offices_return_both_guides_in_order():
    regent = RoleGuideFactory(role="regent", order=1)
    risk = RoleGuideFactory(role="risk management chair", order=5)
    assert services.get_role_guides(_officer("regent", "risk management chair")) == [regent, risk]


def test_an_inactive_guide_is_never_mine():
    RoleGuideFactory(role="treasurer", is_active=False)
    assert services.get_role_guides(_officer("treasurer")) == []


def test_an_impersonated_role_gets_that_roles_guide():
    """A national officer previewing as a Treasurer must see the Treasurer guide."""
    from thetatauCMT.users.tests.factories import UserAlterFactory

    guide = RoleGuideFactory(role="treasurer")
    user = _in_group(_member(), "natoff")
    UserAlterFactory(user=user, chapter=user.chapter, role="treasurer")
    assert services.get_role_guides(user) == [guide]


def test_every_national_officer_gets_the_national_guide():
    """There are eighteen national roles and one shared national surface.

    A Grand Regent holds none of the roles a guide is written for, so without
    this they would have no guide at all.
    """
    national = RoleGuideFactory(role="national officer")
    RoleGuideFactory(role="treasurer")

    assert services.get_role_guides(_natoff("grand regent")) == [national]


def test_a_regional_director_gets_both_their_own_guide_and_the_national_one():
    national = RoleGuideFactory(role="national officer", order=9)
    regional = RoleGuideFactory(role="regional director", order=8)

    assert services.get_role_guides(_natoff("regional director")) == [regional, national]


def test_a_chapter_officer_does_not_get_the_national_guide():
    RoleGuideFactory(role="national officer")
    treasurer = RoleGuideFactory(role="treasurer")

    assert services.get_role_guides(_officer("treasurer")) == [treasurer]


def test_viewing_as_a_member_gives_up_the_national_guide():
    """The "hide national officer functionality" toggle has to reach this too."""
    from thetatauCMT.users.tests.factories import UserAlterFactory

    RoleGuideFactory(role="national officer")
    user = _natoff("grand regent")
    UserAlterFactory(user=user, chapter=user.chapter, role=None, hide_natoff=True)

    assert services.get_role_guides(user) == []


# ---------------------------------------------------------------------------
# get_role_guide_detail -- open items
# ---------------------------------------------------------------------------
def test_open_items_are_scoped_to_the_role():
    user = _officer("treasurer")
    guide = RoleGuideFactory(role="treasurer")
    mine = _task("treasurer", "Pay the invoice", user.current_chapter)
    _task("scribe", "File the minutes", user.current_chapter)

    items = services.get_role_guide_detail(guide, user)["open_items"]

    assert list(items.values_list("task__name", flat=True)).count("Pay the invoice") == 1
    assert "File the minutes" not in list(items.values_list("task__name", flat=True))
    assert mine.owner == "treasurer"


def test_open_items_exclude_dates_this_chapter_has_completed():
    user = _officer("treasurer")
    guide = RoleGuideFactory(role="treasurer")
    task = _task("treasurer", "Pay the invoice", user.current_chapter)
    due = task.dates.first()

    assert "Pay the invoice" in _names(services.get_role_guide_detail(guide, user)["open_items"])

    TaskChapter.objects.create(task=due, chapter=user.current_chapter, date=timezone.now())
    assert "Pay the invoice" not in _names(services.get_role_guide_detail(guide, user)["open_items"])


def test_open_items_exclude_archived_dates():
    user = _officer("treasurer")
    guide = RoleGuideFactory(role="treasurer")
    _task("treasurer", "Retired obligation", user.current_chapter, archived=True)

    assert "Retired obligation" not in _names(services.get_role_guide_detail(guide, user)["open_items"])


def test_another_chapters_completion_does_not_close_out_mine():
    """``TaskDate`` rows are national; only the completion is per chapter.

    Worth pinning down, because it is the one place a guide could quietly tell an
    officer they are done when they are not.
    """
    mine = _officer("treasurer")
    theirs = _officer("treasurer")
    guide = RoleGuideFactory(role="treasurer")
    task = _task("treasurer", "Shared obligation", mine.current_chapter)
    TaskChapter.objects.create(task=task.dates.first(), chapter=theirs.current_chapter, date=timezone.now())

    assert "Shared obligation" in _names(services.get_role_guide_detail(guide, mine)["open_items"])
    assert "Shared obligation" not in _names(services.get_role_guide_detail(guide, theirs)["open_items"])


def _names(items):
    return list(items.values_list("task__name", flat=True))


# ---------------------------------------------------------------------------
# get_role_guide_detail -- steps and tools
# ---------------------------------------------------------------------------
def test_a_step_pointing_at_an_invisible_feature_is_dropped():
    """Advertising a page that would bounce them is worse than a shorter list."""
    guide = RoleGuideFactory(role="treasurer")
    visible = FeatureFactory(key="member-thing", audience=Audience.MEMBER)
    hidden = FeatureFactory(key="natoff-thing", audience=Audience.NATOFF)
    RoleGuideStepFactory(guide=guide, title="Do the visible thing", feature=visible, order=1)
    RoleGuideStepFactory(guide=guide, title="Do the hidden thing", feature=hidden, order=2)
    RoleGuideStepFactory(guide=guide, title="Do the plain thing", feature=None, order=3)

    steps = services.get_role_guide_detail(guide, _officer("treasurer"))["steps"]

    assert [entry["step"].title for entry in steps] == ["Do the visible thing", "Do the plain thing"]


def test_a_step_carries_the_resolved_url():
    guide = RoleGuideFactory(role="treasurer")
    RoleGuideStepFactory(guide=guide, feature=FeatureFactory(key="linked", url_name="home"))

    steps = services.get_role_guide_detail(guide, _officer("treasurer"))["steps"]

    assert steps[0]["url"] == reverse("home")


def test_tools_are_the_features_tagged_with_this_role():
    guide = RoleGuideFactory(role="treasurer")
    FeatureFactory(key="mine-dues", roles=["treasurer"])
    FeatureFactory(key="mine-minutes", roles=["scribe"])

    tools = services.get_role_guide_detail(guide, _officer("treasurer"))["tools"]

    keys = [tool.key for tool in tools if tool.key.startswith("mine-")]
    assert keys == ["mine-dues"]


def test_tools_include_a_duty_the_task_carries_rather_than_the_roles_field():
    """The Audit is five ``Task`` rows, and a feature can only link one of them.

    Tagging that entry ``["treasurer"]`` would keep it off the other four guides
    even though all five officers owe it, so membership is the derived role set.
    """
    user = _officer("scribe")
    guide = RoleGuideFactory(role="scribe")
    Task.objects.create(name="Audit", owner="scribe", type="task", description="Audit")
    linked = Task.objects.create(name="Audit", owner="treasurer", type="task", description="Audit")
    FeatureFactory(key="mine-audit", roles=[], task=linked)

    tools = services.get_role_guide_detail(guide, user)["tools"]

    assert [tool.key for tool in tools if tool.key.startswith("mine-")] == ["mine-audit"]


# ---------------------------------------------------------------------------
# get_role_guide_detail -- national officer tools
# ---------------------------------------------------------------------------
def test_a_national_guide_also_lists_the_untagged_national_tools():
    """National pages are audience-gated, not role-tagged.

    Without this the Regional Director guide would list their four region pages
    and none of the national ones they can equally reach.
    """
    guide = RoleGuideFactory(role="regional director")
    FeatureFactory(key="mine-region-tasks", roles=["regional director"], audience=Audience.NATOFF)
    FeatureFactory(key="mine-national-dashboard", audience=Audience.NATOFF)
    FeatureFactory(key="mine-member-thing", audience=Audience.MEMBER)

    detail = services.get_role_guide_detail(guide, _natoff())

    assert [tool.key for tool in detail["tools"] if tool.key.startswith("mine-")] == ["mine-region-tasks"]
    assert [tool.key for tool in detail["national_tools"] if tool.key.startswith("mine-")] == [
        "mine-national-dashboard"
    ]


def test_a_chapter_office_gets_no_national_tools_block():
    guide = RoleGuideFactory(role="treasurer")
    FeatureFactory(key="mine-natoff", audience=Audience.NATOFF)

    assert services.get_role_guide_detail(guide, _natoff())["national_tools"] == []


def test_a_member_reading_a_national_guide_is_not_shown_pages_they_cannot_open():
    guide = RoleGuideFactory(role="regional director")
    FeatureFactory(key="mine-natoff", audience=Audience.NATOFF)

    assert services.get_role_guide_detail(guide, _member())["national_tools"] == []


def test_query_count_does_not_grow_with_the_number_of_steps():
    guide = RoleGuideFactory(role="treasurer")
    user = _officer("treasurer")
    for index in range(2):
        RoleGuideStepFactory(guide=guide, feature=FeatureFactory(key=f"small-{index}"), order=index)
    services.get_role_guide_detail(guide, user)  # warm caches

    with CaptureQueriesContext(connection) as small:
        services.get_role_guide_detail(guide, user)
    for index in range(20):
        RoleGuideStepFactory(guide=guide, feature=FeatureFactory(key=f"large-{index}"), order=index + 10)
    with CaptureQueriesContext(connection) as large:
        services.get_role_guide_detail(guide, user)

    assert len(large) == len(small)


# ---------------------------------------------------------------------------
# The pages
# ---------------------------------------------------------------------------
def test_every_seeded_role_guide_renders(auto_login_user, feature_registry):
    """All ten shipped guides, against the real registry."""
    client, _ = auto_login_user()
    guides = RoleGuide.objects.active()
    assert guides.count() == 10
    for guide in guides:
        response = client.get(guide.get_absolute_url())
        assert response.status_code == 200, guide.role
        assert guide.title in response.content.decode()


def test_an_unknown_slug_is_a_404(auto_login_user):
    client, _ = auto_login_user()
    assert client.get(reverse("guides:role-guide", kwargs={"slug": "wizard"})).status_code == 404


def test_the_regional_director_page_shows_the_national_tools(auto_login_user, feature_registry):
    """Against the real registry: the RD guide is the national-officer landing page."""
    client, user = auto_login_user()
    _in_group(user, "natoff")
    user.current_roles = ["regional director"]
    user.save(update_fields=["current_roles"])

    body = client.get(reverse("guides:role-guide", kwargs={"slug": "regional-director"})).content.decode()

    assert "National officer tools" in body
    assert "National dashboard" in body


def test_a_member_with_no_office_gets_the_index_not_a_404(auto_login_user):
    client, _ = auto_login_user()
    RoleGuideFactory(role="treasurer", title="Treasurer")

    response = client.get(reverse("guides:role-guides"))

    assert response.status_code == 200
    assert "Treasurer" in response.content.decode()


def test_one_office_redirects_straight_to_that_guide(auto_login_user):
    client, user = auto_login_user()
    guide = RoleGuideFactory(role="treasurer")
    user.current_roles = ["treasurer"]
    user.save(update_fields=["current_roles"])

    response = client.get(reverse("guides:role-guides"))

    assert response.status_code == 302
    assert response["Location"] == guide.get_absolute_url()


def test_the_guide_page_badges_your_own_role(auto_login_user):
    client, user = auto_login_user()
    guide = RoleGuideFactory(role="treasurer")
    user.current_roles = ["treasurer"]
    user.save(update_fields=["current_roles"])

    body = client.get(guide.get_absolute_url()).content.decode()

    assert "This is your role" in body


def test_the_guide_page_is_readable_for_a_role_you_do_not_hold(auto_login_user):
    """Guides are reference material, not access control -- anyone may read one."""
    client, _ = auto_login_user()
    guide = RoleGuideFactory(role="treasurer")

    response = client.get(guide.get_absolute_url())

    assert response.status_code == 200
    assert "This is your role" not in response.content.decode()


def test_the_home_page_offers_your_guide(auto_login_user):
    client, user = auto_login_user()
    RoleGuideFactory(role="treasurer", title="Treasurer")
    user.current_roles = ["treasurer"]
    user.save(update_fields=["current_roles"])

    body = client.get(reverse("home")).content.decode()

    assert 'data-role-guide="treasurer"' in body


def test_the_account_menu_always_links_to_the_guides(auto_login_user):
    client, _ = auto_login_user()
    body = client.get(reverse("home")).content.decode()
    assert reverse("guides:role-guides") in body


def test_the_guides_pages_require_sign_in(client):
    for url in [reverse("guides:role-guides"), reverse("guides:role-guide", kwargs={"slug": "treasurer"})]:
        assert client.get(url).status_code == 302
