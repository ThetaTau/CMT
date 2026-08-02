"""The rebuilt Forms landing page (TWI-9b).

The old page was a hand-maintained list of links. The new one renders from the
feature registry, which is a strictly better arrangement *except* for one risk:
a form can now disappear from the page because somebody forgot a registry entry,
and nobody would notice until a chapter missed a deadline. The snapshot test
below is the guard against exactly that.
"""

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.forms.views import FORM_GROUPS
from thetatauCMT.guides import services as guide_services
from thetatauCMT.guides.models import Feature, FeatureArea
from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate

pytestmark = pytest.mark.django_db

#: Every URL name the pre-rebuild landing template linked to, captured before it
#: was deleted. Nothing here may fall off the page without a line in
#: ``DOCUMENTED_EXCLUSIONS`` explaining why.
PRE_REBUILD_URL_NAMES = {
    "attendance:match_queue",
    "attendance:national_upload",
    "awards:direct_grant",
    "awards:directory",
    "ballots:votelist",
    "conventionform",
    "forms:alumniexclusion_list",
    "forms:audit",
    "forms:audit_list",
    "forms:bylaws",
    "forms:bylaws_list",
    "forms:collection",
    "forms:convention_list",
    "forms:education_list",
    "forms:init_selection",
    "forms:natoff",
    "forms:officer",
    "forms:osm_list",
    "forms:pledge_pins",
    "forms:pledge_program_list",
    "forms:pledgeform",
    "forms:resign_list",
    "forms:ritual_proficiency",
    "forms:rmp",
    "forms:rmp_list",
    "forms:status_history",
    "gear",
    "nominations:list",
    "osmform",
    "submissions:gearlist",
    "viewflow:awards:awardnomination:start",
    "viewflow:forms:disciplinaryprocess:start",
    "viewflow:forms:hseducation:start",
    "viewflow:forms:prematurealumnus:start",
    "viewflow:forms:returnstudent:start",
    "viewflow:nominations:nomination:start",
}

#: Deliberate departures, each one a decision rather than an oversight.
DOCUMENTED_EXCLUSIONS = {
    # Permanent redirects to their Viewflow replacements; the registry links the
    # destination, so the form is still on the page under its real URL.
    "alumniexclusion": "viewflow:forms:alumniexclusion:start",
    "forms:pledge_program": "viewflow:forms:pledgeprogramprocess:start",
    # SuperuserRequiredMixin internal tooling. Not catalogued (TWI-8 decision);
    # it lives in the Administrator tools block at the bottom of the page.
    "awards:import_upload": "superuser-only",
    # The viewflow frontend inbox. Admin tooling a chapter officer cannot reach;
    # their outstanding process tasks are on tasks:list instead.
    "viewflow:index": "superuser-only",
}


def _in_group(user, name):
    user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def _rendered_url_names(user):
    """Every registry URL name the landing page would render for ``user``."""
    groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")
    return {entry["feature"].url_name for group in groups for entry in group["entries"] if entry["feature"].url_name}


# ---------------------------------------------------------------------------
# The snapshot
# ---------------------------------------------------------------------------
def test_no_form_disappeared_from_the_landing_page(feature_registry, auto_login_user):
    """Every link the old page had is still on the new one, for someone who can use it."""
    _, user = auto_login_user()
    _in_group(user, "officer")
    _in_group(user, "natoff")

    missing = PRE_REBUILD_URL_NAMES - _rendered_url_names(user)

    assert missing == set(), f"dropped from the forms landing: {sorted(missing)}"


def test_the_documented_exclusions_are_still_the_only_ones(feature_registry, auto_login_user):
    """Fails loudly if an excluded URL quietly comes back, or a new one is dropped."""
    _, user = auto_login_user()
    _in_group(user, "officer")
    _in_group(user, "natoff")

    rendered = _rendered_url_names(user)

    assert "awards:import_upload" not in rendered
    assert "viewflow:forms:alumniexclusion:start" in rendered
    assert "viewflow:forms:pledgeprogramprocess:start" in rendered


# ---------------------------------------------------------------------------
# Audience
# ---------------------------------------------------------------------------
def test_a_member_does_not_see_officer_forms(feature_registry, auto_login_user):
    """Asserted over the registry entries, not the HTML -- the nav links some of
    these pages too, so a body search would test the wrong thing."""
    _, user = auto_login_user()

    rendered = _rendered_url_names(user)

    assert "forms:officer_add" not in rendered
    assert "forms:audit" not in rendered
    # The roster itself stays member-visible on purpose: knowing who your own
    # officers are is not privileged.
    assert "forms:officer" in rendered


def test_an_officer_sees_officer_forms(feature_registry, auto_login_user):
    _, user = auto_login_user()
    _in_group(user, "officer")

    rendered = _rendered_url_names(user)

    assert "forms:officer_add" in rendered
    assert "forms:audit" in rendered


def test_administrator_tools_are_superuser_only(feature_registry, auto_login_user, settings):
    # Superusers are pushed into 2FA setup outside DEBUG, which would swallow the
    # page before the template is reached.
    settings.DEBUG = True
    client, user = auto_login_user()
    _in_group(user, "natoff")
    assert reverse("awards:import_upload") not in client.get(reverse("forms:landing")).content.decode()

    user.is_superuser = True
    user.save(update_fields=["is_superuser"])
    assert reverse("awards:import_upload") in client.get(reverse("forms:landing")).content.decode()


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------
def test_every_group_that_has_content_is_rendered(feature_registry, auto_login_user):
    client, user = auto_login_user()
    _in_group(user, "officer")
    _in_group(user, "natoff")

    body = client.get(reverse("forms:landing")).content.decode()

    for group in FORM_GROUPS:
        assert group["label"] in body, group["key"]


def test_unclaimed_forms_area_entries_fall_into_everything_else(feature_registry, auto_login_user):
    """Adding a registry entry must never make a form silently vanish."""
    _, user = auto_login_user()
    Feature.objects.create(
        area=FeatureArea.objects.get(key="forms-workflows"),
        key="ungrouped-thing",
        name="Ungrouped thing",
        short_description="Belongs to no group.",
    )

    groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")
    leftovers = [group for group in groups if group["key"] == "other"]

    assert leftovers, "the fallback group did not appear"
    assert "ungrouped-thing" in {entry["feature"].key for entry in leftovers[0]["entries"]}


def test_the_page_points_at_the_catalog(feature_registry, auto_login_user):
    client, _ = auto_login_user()
    assert reverse("guides:catalog") in client.get(reverse("forms:landing")).content.decode()


# ---------------------------------------------------------------------------
# Accordion
#
# ``static/js/catalog.js`` drives both this page and the catalog by querying a
# handful of hooks. Renaming one silently reverts the page to a flat, unfiltered
# list, which nothing else here would notice.
# ---------------------------------------------------------------------------
def test_each_group_is_a_collapsible_panel_a_chip_can_open(feature_registry, auto_login_user):
    client, user = auto_login_user()
    _in_group(user, "officer")
    _in_group(user, "natoff")

    body = client.get(reverse("forms:landing")).content.decode()

    for group in FORM_GROUPS:
        # The section id is also the deep link target, so it has to survive.
        assert f'id="forms-{group["key"]}"' in body, group["key"]
        assert f'data-catalog-area="{group["key"]}"' in body, group["key"]
        assert f'id="panel-{group["key"]}"' in body, group["key"]
        assert f'data-catalog-chip="{group["key"]}"' in body, group["key"]
        assert group["chip"] in body, group["key"]


def test_the_panels_start_closed(feature_registry, auto_login_user):
    """Arriving at a wall of open tables is the flat list the accordion replaced."""
    client, user = auto_login_user()
    _in_group(user, "officer")

    body = client.get(reverse("forms:landing")).content.decode()

    assert 'class="accordion-collapse collapse show' not in body


def test_the_script_finds_its_controls(feature_registry, auto_login_user):
    client, user = auto_login_user()
    _in_group(user, "officer")
    user.current_roles = ["treasurer"]
    user.save(update_fields=["current_roles"])

    body = client.get(reverse("forms:landing")).content.decode()

    for hook in (
        'id="tt-catalog-search"',
        'id="tt-catalog-chips"',
        'id="tt-catalog-expand"',
        'id="tt-catalog-count"',
        'id="tt-catalog-mine"',
        'id="tt-catalog-mine-section"',
        "js/catalog.js",
    ):
        assert hook in body, hook


def test_your_own_duties_are_a_panel_the_filters_leave_alone(feature_registry, auto_login_user):
    """The pinned panel indexes duties, not search results: it carries no cards,
    so the counts and the area filter have to skip over it."""
    client, user = auto_login_user()
    _in_group(user, "officer")
    user.current_roles = ["treasurer"]
    user.save(update_fields=["current_roles"])

    body = client.get(reverse("forms:landing")).content.decode()
    start = body.index('id="tt-catalog-mine-section"')
    # The panel runs from its own id up to the first real, filterable group.
    pinned = body[start : body.index("tt-catalog-section", start)]

    assert "tt-catalog-card" not in pinned
    assert "data-catalog-area" not in pinned


def test_a_member_with_no_office_gets_no_pinned_panel(feature_registry, auto_login_user):
    client, _ = auto_login_user()

    body = client.get(reverse("forms:landing")).content.decode()

    assert 'id="tt-catalog-mine-section"' not in body
    assert 'id="tt-catalog-mine"' not in body


# ---------------------------------------------------------------------------
# "For your role"
# ---------------------------------------------------------------------------
def test_the_pinned_block_holds_the_viewers_own_forms(feature_registry, auto_login_user):
    client, user = auto_login_user()
    _in_group(user, "officer")
    user.current_roles = ["treasurer"]
    user.save(update_fields=["current_roles"])

    response = client.get(reverse("forms:landing"))

    pinned = {entry["feature"].key: entry["roles"] for entry in response.context["mine"]}
    assert pinned, "a treasurer saw no forms pinned to their role"
    assert [key for key, roles in pinned.items() if "treasurer" not in roles] == []


def test_the_audit_names_every_officer_who_has_to_submit_one(feature_registry, auto_login_user):
    """The Audit is five ``Task`` rows, one per officer, and a feature can link
    only one of them -- listing that row's owner alone calls it a Treasurer job."""
    client, user = auto_login_user()
    _in_group(user, "officer")

    groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")

    assert _entry(groups, "chapter-audit-form")["roles"] == [
        "regent",
        "vice regent",
        "scribe",
        "treasurer",
        "corresponding secretary",
    ]


def test_a_per_member_filing_names_no_officer_at_all(feature_registry, auto_login_user):
    """``RiskManagement`` is one row per user per term, so no role owes it --
    the registry used to advertise it as a Regent/Risk Management Chair duty."""
    client, user = auto_login_user()
    _in_group(user, "officer")

    groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")

    assert _entry(groups, "risk-management-policies")["roles"] == []
    assert "Every member" in client.get(reverse("forms:landing")).content.decode()


def test_the_pinned_block_is_empty_for_a_member_with_no_office(feature_registry, auto_login_user):
    client, _ = auto_login_user()

    assert client.get(reverse("forms:landing")).context["mine"] == []


# ---------------------------------------------------------------------------
# Due dates
# ---------------------------------------------------------------------------
def _link_task_to(feature_key, chapter, days=10):
    """Give the registry entry a task with one upcoming date for ``chapter``."""
    feature = Feature.objects.get(key=feature_key)
    task = Task.objects.create(name=f"Task for {feature_key}", owner="treasurer", type="task", description="x")
    TaskDate.objects.create(
        task=task,
        school_type=chapter.school_type,
        date=timezone.now().date() + timedelta(days=days),
    )
    feature.task = task
    feature.save(update_fields=["task"])
    return task


def _entry(groups, key):
    return next(entry for group in groups for entry in group["entries"] if entry["feature"].key == key)


def test_a_due_date_shows_only_while_the_chapter_still_owes_it(feature_registry, auto_login_user):
    _, user = auto_login_user()
    _in_group(user, "officer")
    task = _link_task_to("chapter-audit-form", user.current_chapter)

    groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")
    assert _entry(groups, "chapter-audit-form")["due"] is not None

    TaskChapter.objects.create(task=task.dates.first(), chapter=user.current_chapter, date=timezone.now())

    groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")
    assert _entry(groups, "chapter-audit-form")["due"] is None


def test_a_form_with_no_task_carries_no_due_date(feature_registry, auto_login_user):
    _, user = auto_login_user()
    _in_group(user, "officer")

    groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")

    assert _entry(groups, "pledge-pins")["due"] is None


# ---------------------------------------------------------------------------
# Cadence
#
# "How often", from the recurring dates `manage.py task_dates` seeds out of
# date_data.csv -- not from how many rows happen to sit in this calendar year.
# ---------------------------------------------------------------------------
def _cadence_of(user, feature_key):
    groups = guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")
    return _entry(groups, feature_key)["cadence"]


def test_an_annual_form_still_reads_once_a_year_after_its_date_is_archived(feature_registry, auto_login_user):
    """Old dates are archived, so counting this year's rows would blank the cadence."""
    _, user = auto_login_user()
    _in_group(user, "officer")
    task = _link_task_to("chapter-audit-form", user.current_chapter)
    task.dates.update(date=timezone.now().date() - timedelta(days=200), archived=True)

    assert _cadence_of(user, "chapter-audit-form") == "Once a year"


def test_a_form_due_more_than_once_a_year_reads_every_term(feature_registry, auto_login_user):
    _, user = auto_login_user()
    _in_group(user, "officer")
    task = _link_task_to("chapter-audit-form", user.current_chapter)
    TaskDate.objects.create(
        task=task,
        school_type=user.current_chapter.school_type,
        date=timezone.now().date() + timedelta(days=180),
    )

    assert _cadence_of(user, "chapter-audit-form") == "Every term"


def test_one_deadline_owed_by_five_officers_is_not_five_deadlines(feature_registry, auto_login_user):
    """The Audit is five ``Task`` rows on one date; counting rows would say "Every term"."""
    _, user = auto_login_user()
    _in_group(user, "officer")
    task = _link_task_to("chapter-audit-form", user.current_chapter)
    day = task.dates.first().date
    for owner in ("regent", "vice regent", "scribe", "corresponding secretary"):
        sibling = Task.objects.create(name=task.name, owner=owner, type="task", description="x")
        TaskDate.objects.create(task=sibling, school_type=user.current_chapter.school_type, date=day)

    assert _cadence_of(user, "chapter-audit-form") == "Once a year"


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------
def test_due_dates_do_not_cost_a_query_per_row(feature_registry, auto_login_user):
    """The page lists ~40 forms; a per-card lookup would be 40 queries."""
    _, user = auto_login_user()
    _in_group(user, "officer")

    def count():
        with CaptureQueriesContext(connection) as queries:
            guide_services.get_feature_groups(user, FORM_GROUPS, fallback_area_key="forms-workflows")
        return len(queries)

    _link_task_to("chapter-audit-form", user.current_chapter)
    count()  # warm the content-type and permission caches, which are one-time costs
    one = count()
    for key in ("collection-referral", "chapter-bylaws", "risk-management-policies"):
        _link_task_to(key, user.current_chapter)

    assert count() == one
