"""CSSWI-8: the CSS landing page ("My Chapters"), its dashboard scope, and Home."""

import datetime
import json

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django_userforeignkey.request import set_current_request

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.dashboard import SUPPORT_SCOPE, get_scope_chapters, populate_support_chapters, store_region
from thetatauCMT.support.overview import chapter_overview
from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate
from thetatauCMT.users.models import User
from thetatauCMT.users.tests.factories import UserFactory

from .factories import ChapterSupportAssignmentFactory, give_css_role, make_css, make_regent

pytestmark = pytest.mark.django_db


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def _fresh(user):
    return User.objects.get(pk=user.pk)


def assigned_css(*names, **kwargs):
    css = make_css(**kwargs)
    chapters = [ChapterFactory(name=name) for name in names]
    for chapter in chapters:
        ChapterSupportAssignmentFactory(user=css, chapter=chapter)
    return _fresh(css), chapters


def _natoff(user):
    Group.objects.get_or_create(name="natoff")[0].user_set.add(user)
    return _fresh(user)


# --- Home and signing in (Q24 A) ------------------------------------------------------------


def test_home_and_signing_in_open_my_chapters_for_a_css(auto_login_user):
    css, _ = assigned_css("alpha")
    client, _ = auto_login_user(user=css)

    assert client.get(reverse("home"))["Location"] == reverse("support:my_chapters")
    assert client.get(reverse("users:redirect"))["Location"] == reverse("support:my_chapters")


def test_a_member_css_can_still_open_their_member_home(auto_login_user):
    member = UserFactory(status="alumni", chapter=ChapterFactory(name="alpha"))
    give_css_role(member)
    ChapterSupportAssignmentFactory(user=member, chapter=ChapterFactory(name="beta"))
    client, _ = auto_login_user(user=_fresh(member))

    assert client.get(reverse("home"))["Location"] == reverse("support:my_chapters")
    assert client.get(reverse("home"), {"member": "1"}).status_code == 200
    content = client.get(reverse("support:my_chapters")).content.decode()
    assert f'{reverse("home")}?member=1' in content


@pytest.mark.parametrize("who", ["member", "national officer who is also a css"])
def test_everyone_else_keeps_their_home_and_is_sent_away_from_my_chapters(auto_login_user, who):
    if who == "member":
        user = UserFactory(status="active")
    else:
        user, _ = assigned_css("alpha")
        user = _natoff(user)
    client, _ = auto_login_user(user=user)

    assert client.get(reverse("home")).status_code == 200
    assert client.get(reverse("support:my_chapters"))["Location"] == reverse("home")


# --- the table (Q12) ----------------------------------------------------------------------------


def test_only_current_assignments_are_listed(auto_login_user):
    css, (alpha, beta) = assigned_css("alpha", "beta")
    ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="delta"), start=_days(-30), end=_days(-1))
    ChapterSupportAssignmentFactory(user=css, chapter=ChapterFactory(name="epsilon"), start=_days(5))
    client, _ = auto_login_user(user=_fresh(css))

    content = client.get(reverse("support:my_chapters")).content.decode()
    table = content.split('id="css-my-chapters"')[1].split("</table>")[0]

    assert alpha.name in table and beta.name in table
    assert "delta" not in table.lower() and "epsilon" not in table.lower()
    # Every chapter but the one being viewed gets a switch button.
    assert table.count(reverse("support:switch")) == 1 and "Viewing" in table


def test_the_numbers_match_each_chapters_own_pages():
    alpha = ChapterFactory(name="alpha")
    beta = ChapterFactory(name="beta")
    for _ in range(2):
        UserFactory(chapter=alpha, status="active")
    UserFactory(chapter=alpha, status="pnm")
    UserFactory(chapter=alpha, status="alumni")
    make_regent(chapter=alpha)
    task = Task.objects.first()
    overdue = TaskDate.objects.create(task=task, date=_days(-12), school_type=alpha.school_type)
    done = TaskDate.objects.create(task=task, date=_days(-11), school_type=alpha.school_type)
    TaskChapter.objects.create(task=done, chapter=alpha)
    TaskDate.objects.create(task=task, date=_days(9), school_type=alpha.school_type)

    rows = {row["chapter"].pk: row for row in chapter_overview([alpha, beta])}

    for chapter in (alpha, beta):
        row = rows[chapter.pk]
        assert row["actives"] == chapter.actives().count()
        assert row["pnms"] == chapter.pledges().count()
        expected_overdue = TaskDate.incomplete_dates_for_chapter(chapter).filter(date__lt=timezone.localdate())
        assert row["overdue"] == expected_overdue.count()
    assert overdue in TaskDate.incomplete_dates_for_chapter(alpha)
    assert rows[alpha.pk]["actives"] == 3  # the two actives and the Regent
    assert rows[alpha.pk]["missing"] == ["Scribe", "Vice Regent", "Treasurer", "Corresponding Secretary"]
    assert rows[beta.pk]["missing"][0] == "Regent"


def test_the_table_costs_the_same_queries_however_many_chapters():
    one = [ChapterFactory(name="alpha")]
    three = [ChapterFactory(name=name) for name in ("beta", "delta", "epsilon")]
    for chapter in one + three:
        UserFactory(chapter=chapter, status="active")

    with CaptureQueriesContext(connection) as small:
        chapter_overview(one)
    with CaptureQueriesContext(connection) as large:
        chapter_overview(three)

    assert len(small) == len(large) <= 4


# --- the dashboard is held to their chapters on the server (Q12 C) -------------------------------


@pytest.fixture
def as_viewer():
    tokens = []

    def bind(user):
        request = RequestFactory().get("/")
        request.user = user
        tokens.append(set_current_request(request))

    yield bind
    set_current_request(None)


def _slugs(queryset):
    return sorted(chapter.slug for chapter in queryset)


def test_a_css_sees_only_their_chapters_whatever_scope_is_asked_for(as_viewer):
    css, (alpha, beta) = assigned_css("alpha", "beta")
    delta = ChapterFactory(name="delta", region=alpha.region)
    as_viewer(css)

    assert _slugs(get_scope_chapters(SUPPORT_SCOPE)) == sorted([alpha.slug, beta.slug])
    assert _slugs(get_scope_chapters("national")) == sorted([alpha.slug, beta.slug])
    assert delta.slug not in _slugs(get_scope_chapters(alpha.region.slug))
    assert _slugs(get_scope_chapters(f"chapter_{delta.slug}")) == []
    assert _slugs(get_scope_chapters(f"chapter_{beta.slug}")) == [beta.slug]


def test_a_member_css_also_keeps_their_own_chapter(as_viewer):
    own = ChapterFactory(name="alpha")
    member = UserFactory(status="alumni", chapter=own)
    give_css_role(member)
    beta = ChapterFactory(name="beta")
    ChapterSupportAssignmentFactory(user=member, chapter=beta)
    as_viewer(_fresh(member))

    assert _slugs(get_scope_chapters(f"chapter_{own.slug}")) == [own.slug]
    assert _slugs(get_scope_chapters(SUPPORT_SCOPE)) == [beta.slug]


def test_everyone_else_is_unchanged(as_viewer):
    css, (alpha,) = assigned_css("alpha")
    ChapterFactory(name="beta")
    member = UserFactory(status="active")
    every = _slugs(get_scope_chapters("national"))

    as_viewer(_natoff(css))
    assert _slugs(get_scope_chapters("national")) == every
    as_viewer(member)
    assert _slugs(get_scope_chapters("national")) == every
    assert _slugs(get_scope_chapters(SUPPORT_SCOPE)) == []


def test_the_chapter_filter_lists_only_their_chapters(as_viewer):
    css, (alpha, beta) = assigned_css("alpha", "beta")
    ChapterFactory(name="delta")
    as_viewer(css)

    options, value, style = populate_support_chapters(SUPPORT_SCOPE)

    assert [option["value"] for option in options] == [SUPPORT_SCOPE, f"chapter_{alpha.slug}", f"chapter_{beta.slug}"]
    assert value == SUPPORT_SCOPE and style != {"display": "none"}
    assert populate_support_chapters(None) == ([], None, {"display": "none"})
    assert store_region("national", SUPPORT_SCOPE, f"chapter_{alpha.slug}") == f"chapter_{alpha.slug}"
    assert store_region("national", SUPPORT_SCOPE, None) == SUPPORT_SCOPE


def test_an_edited_dashboard_request_still_shows_only_their_chapters(auto_login_user):
    css, (alpha,) = assigned_css("alpha")
    delta = ChapterFactory(name="delta")
    for chapter in (alpha, delta):
        UserFactory(chapter=chapter, status="active")
    client, _ = auto_login_user(user=css)
    payload = {
        "output": "members-by-chapter.figure",
        "outputs": {"id": "members-by-chapter", "property": "figure"},
        "inputs": [
            {"id": "region-slug-store", "property": "data", "value": "national"},
            {"id": "theme-store", "property": "data", "value": "light"},
        ],
        "changedPropIds": ["region-slug-store.data"],
        "state": [],
    }

    response = client.post(
        "/django_plotly_dash/app/RegionDashboard/_dash-update-component",
        data=json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200, response.content[:500]
    body = response.content.decode()
    assert alpha.name in body and delta.name not in body
