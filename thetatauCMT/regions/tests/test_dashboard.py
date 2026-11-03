"""Unit tests for `thetatauCMT.regions.dashboard`.

Covers pure helpers (`parse_region_slug`, `_theme_template`, `_apply_theme`,
`_empty_figure`, `_bar_by_chapter`, `region_options`, `get_scope_chapters`)
and integration-lite invocations of the KPI + graph callbacks against the
test DB.
"""

import datetime
from decimal import Decimal

import plotly.graph_objects as go
import pytest
from django.utils import timezone

# ---------------------------------------------------------------------------
# parse_region_slug
# ---------------------------------------------------------------------------


def test_parse_region_slug_national_when_none():
    from thetatauCMT.regions.dashboard import parse_region_slug

    assert parse_region_slug(None) == "national"


def test_parse_region_slug_national_when_root():
    from thetatauCMT.regions.dashboard import parse_region_slug

    assert parse_region_slug("/") == "national"


def test_parse_region_slug_from_region_url():
    from thetatauCMT.regions.dashboard import parse_region_slug

    assert parse_region_slug("/regions/west/") == "west"


def test_parse_region_slug_from_region_url_no_trailing_slash():
    from thetatauCMT.regions.dashboard import parse_region_slug

    assert parse_region_slug("/regions/midwest") == "midwest"


def test_parse_region_slug_national_for_non_region_path():
    from thetatauCMT.regions.dashboard import parse_region_slug

    assert parse_region_slug("/chapters/kelly-johnson/") == "national"


# ---------------------------------------------------------------------------
# _theme_template + _apply_theme
# ---------------------------------------------------------------------------


def test_theme_template_dark():
    from thetatauCMT.regions.dashboard import _theme_template

    assert _theme_template("dark") == "plotly_dark"


def test_theme_template_light_default():
    from thetatauCMT.regions.dashboard import _theme_template

    assert _theme_template("light") == "plotly_white"
    assert _theme_template("") == "plotly_white"
    assert _theme_template(None) == "plotly_white"


def test_apply_theme_sets_transparent_bg_and_template():
    from thetatauCMT.regions.dashboard import _apply_theme

    fig = go.Figure()
    _apply_theme(fig, "dark")
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"


# ---------------------------------------------------------------------------
# _empty_figure + _bar_by_chapter
# ---------------------------------------------------------------------------


def test_empty_figure_carries_message():
    from thetatauCMT.regions.dashboard import _empty_figure

    fig = _empty_figure("light", "Nothing here")
    assert fig.layout.annotations[0].text == "Nothing here"


def test_bar_by_chapter_returns_empty_figure_for_no_rows():
    from thetatauCMT.regions.dashboard import _bar_by_chapter

    fig = _bar_by_chapter([], "Count", "light")
    assert len(fig.data) == 0  # empty figure: no traces
    assert fig.layout.annotations[0].text == "No data for this period"


def test_bar_by_chapter_returns_bars_for_rows():
    from thetatauCMT.regions.dashboard import _bar_by_chapter

    rows = [
        {"chapter__name": "Alpha", "chapter__region__name": "West", "count": 3},
        {"chapter__name": "Beta", "chapter__region__name": "West", "count": 5},
        {"chapter__name": "Gamma", "chapter__region__name": "East", "count": 2},
    ]
    fig = _bar_by_chapter(rows, "Members", "light")
    assert len(fig.data) == 2  # one trace per region colour


def test_bar_by_chapter_handles_user_chapter_field_names():
    """Some callbacks pull rows through `user__chapter__*` — the helper must
    still rename them into `Chapter`/`Region` for the bar chart."""
    from thetatauCMT.regions.dashboard import _bar_by_chapter

    rows = [
        {"user__chapter__name": "Alpha", "user__chapter__region__name": "West", "count": 4},
    ]
    fig = _bar_by_chapter(rows, "Trainings", "light")
    assert len(fig.data) == 1
    assert fig.data[0].x[0] == "Alpha"


# ---------------------------------------------------------------------------
# _horizontal_bar_top_n + _treemap_from_rows
# ---------------------------------------------------------------------------


def test_horizontal_bar_top_n_empty_rows_returns_empty_figure():
    from thetatauCMT.regions.dashboard import _horizontal_bar_top_n

    fig = _horizontal_bar_top_n([], label_key="Major", value_key="count", x_label="Members", theme="light")
    assert len(fig.data) == 0
    assert fig.layout.annotations[0].text == "No data for this period"


def test_horizontal_bar_top_n_drops_missing_columns():
    """When neither key is present the helper should not raise; it should
    fall through to the empty-figure branch."""
    from thetatauCMT.regions.dashboard import _horizontal_bar_top_n

    rows = [{"other_key": "x", "count": 3}]
    fig = _horizontal_bar_top_n(rows, label_key="Major", value_key="count", x_label="Members", theme="light")
    assert len(fig.data) == 0


def test_horizontal_bar_top_n_orders_largest_on_top_and_caps_at_top_n():
    from thetatauCMT.regions.dashboard import _horizontal_bar_top_n

    rows = [
        {"Chapter": "A", "count": 5},
        {"Chapter": "B", "count": 20},
        {"Chapter": "C", "count": 10},
        {"Chapter": "D", "count": 1},
    ]
    fig = _horizontal_bar_top_n(rows, label_key="Chapter", value_key="count", x_label="Init", theme="light", top_n=3)
    # top_n=3 → the smallest row ("D", 1) is dropped.
    assert set(fig.data[0].y) == {"A", "B", "C"}
    # Largest value ends up last in the y-list (plotly draws bottom→top).
    assert fig.data[0].y[-1] == "B"


def test_horizontal_bar_top_n_uses_region_colors():
    from thetatauCMT.regions.dashboard import _horizontal_bar_top_n

    rows = [
        {"Chapter": "A", "Region": "West", "count": 5},
        {"Chapter": "B", "Region": "East", "count": 20},
    ]
    fig = _horizontal_bar_top_n(
        rows, label_key="Chapter", value_key="count", x_label="Init", theme="light", region_key="Region"
    )
    # A per-bar marker_color list means colors is a tuple/list matching bar count.
    marker_color = fig.data[0].marker.color
    assert hasattr(marker_color, "__len__")
    assert len(marker_color) == 2


def test_treemap_from_rows_empty_returns_empty_figure():
    from thetatauCMT.regions.dashboard import _treemap_from_rows

    fig = _treemap_from_rows([], label_key="Employer", value_key="count", theme="light")
    assert len(fig.data) == 0
    assert fig.layout.annotations[0].text == "No data for this period"


def test_treemap_from_rows_renders_labels_and_values():
    from thetatauCMT.regions.dashboard import _treemap_from_rows

    rows = [
        {"Employer": "Boeing", "count": 3},
        {"Employer": "SpaceX", "count": 5},
    ]
    fig = _treemap_from_rows(rows, label_key="Employer", value_key="count", theme="light")
    assert len(fig.data) == 1
    assert set(fig.data[0].labels) == {"Boeing", "SpaceX"}
    assert sum(fig.data[0].values) == 8


def test_treemap_from_rows_caps_at_top_n():
    from thetatauCMT.regions.dashboard import _treemap_from_rows

    rows = [
        {"Employer": "Boeing", "count": 3},
        {"Employer": "SpaceX", "count": 5},
        {"Employer": "Corner Shop", "count": 1},
    ]
    fig = _treemap_from_rows(rows, label_key="Employer", value_key="count", theme="light", top_n=2)
    assert set(fig.data[0].labels) == {"Boeing", "SpaceX"}


def test_treemap_from_rows_uses_custom_value_label():
    from thetatauCMT.regions.dashboard import _treemap_from_rows

    rows = [
        {"Organization": "IEEE", "count": 4},
        {"Organization": "Tau Beta Pi", "count": 2},
    ]
    fig = _treemap_from_rows(rows, label_key="Organization", value_key="count", theme="light", value_label="Members")
    assert set(fig.data[0].labels) == {"IEEE", "Tau Beta Pi"}
    assert "Members=" in fig.data[0].hovertemplate


# ---------------------------------------------------------------------------
# region_options + get_scope_chapters — need DB
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_region_options_starts_with_national():
    from thetatauCMT.regions.dashboard import region_options

    opts = region_options()
    assert opts[0]["value"] == "national"


@pytest.mark.django_db
def test_get_scope_chapters_national_returns_all_active():
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.regions.dashboard import get_scope_chapters

    expected = Chapter.objects.exclude(active=False).count()
    assert get_scope_chapters("national").count() == expected


@pytest.mark.django_db
def test_get_scope_chapters_candidate_chapter_filter():
    from thetatauCMT.chapters.models import Chapter
    from thetatauCMT.regions.dashboard import get_scope_chapters

    expected = Chapter.objects.filter(active=True, candidate_chapter=True).count()
    assert get_scope_chapters("candidate_chapter").count() == expected


# ---------------------------------------------------------------------------
# Callback smoke tests — should not raise and return the right shape.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_update_kpis_returns_each_card_then_its_note():
    from thetatauCMT.regions.dashboard import KPI_CARDS, update_kpis

    result = update_kpis("national", None)
    assert isinstance(result, tuple)
    assert len(result) == 2 * len(KPI_CARDS)
    for v in result:
        assert isinstance(v, str)
    # Notes only appear for a National Officer on a region page.
    assert result[len(KPI_CARDS) :] == ("",) * len(KPI_CARDS)


@pytest.mark.django_db
def test_ay_options_returns_current_ay_first():
    from thetatauCMT.regions.dashboard import ay_options

    opts = ay_options()
    assert len(opts) >= 1
    # Options are ordered newest-first.
    assert opts[0]["value"] >= opts[-1]["value"]


def test_ay_dates_returns_july_range():
    from thetatauCMT.regions.dashboard import ay_dates

    start, end = ay_dates(2025)
    assert start.year == 2025 and start.month == 7 and start.day == 1
    assert end.year == 2026 and end.month == 7 and end.day == 1


def test_ay_dates_none_defaults_to_current():
    from thetatauCMT.regions.dashboard import ay_dates

    start_default, end_default = ay_dates(None)
    # Any positive year is fine; we just care it doesn't raise.
    assert start_default.year > 2000
    assert (end_default - start_default).days >= 365


@pytest.mark.django_db
@pytest.mark.parametrize(
    "callback_name",
    [
        "initiations_by_chapter",
        "graduates_by_chapter",
        "depledges_by_chapter",
        "events_by_chapter",
        "submissions_by_chapter",
        "tasks_by_chapter",
        "trainings_by_chapter",
        "gpa_by_chapter",
        "service_hours_by_chapter",
        "scores_total_by_chapter",
        "scores_bro_by_chapter",
        "scores_ops_by_chapter",
        "scores_pro_by_chapter",
        "scores_ser_by_chapter",
        "top_recruiting_chapters",
        "retention_by_chapter",
        "graduation_employer_cloud",
        "member_organization_cloud",
        "placement_by_chapter",
        "graduates_by_degree",
    ],
)
def test_ay_dependent_graph_callbacks_return_figure(callback_name):
    from thetatauCMT.regions import dashboard as d

    callback = getattr(d, callback_name)
    fig = callback("national", None, "light")
    assert isinstance(fig, go.Figure)


@pytest.mark.django_db
def test_members_by_chapter_returns_figure():
    """members-by-chapter is AY-independent (uses `current_status` today)."""
    from thetatauCMT.regions.dashboard import members_by_chapter

    fig = members_by_chapter("national", "light")
    assert isinstance(fig, go.Figure)


@pytest.mark.django_db
def test_majors_breakdown_returns_figure():
    """majors-breakdown is AY-independent (snapshot of current members)."""
    from thetatauCMT.regions.dashboard import majors_breakdown

    fig = majors_breakdown("national", "light")
    assert isinstance(fig, go.Figure)


@pytest.mark.django_db
def test_current_employer_cloud_counts_members_per_employer():
    """current-employer-cloud is AY-independent: it reads `User.employer` today."""
    from thetatauCMT.forms.models import Employer
    from thetatauCMT.regions.dashboard import current_employer_cloud
    from thetatauCMT.users.tests.factories import UserFactory

    boeing = Employer.objects.create(name="Boeing Dashboard Test")
    spacex = Employer.objects.create(name="SpaceX Dashboard Test")
    UserFactory.create_batch(2, employer=boeing, current_status="alumni")
    UserFactory(employer=spacex, current_status="active")
    # A departed member's employer is not "where our members work".
    UserFactory(employer=spacex, current_status="expelled")

    fig = current_employer_cloud("national", "light")
    assert isinstance(fig, go.Figure)
    counts = dict(zip(fig.data[0].labels, fig.data[0].values))
    assert counts["Boeing Dashboard Test"] == 2
    assert counts["SpaceX Dashboard Test"] == 1


@pytest.mark.django_db
def test_current_employer_cloud_empty_without_employers():
    from thetatauCMT.regions.dashboard import current_employer_cloud

    fig = current_employer_cloud("national", "light")
    assert len(fig.data) == 0


@pytest.mark.django_db
def test_sync_region_from_url_returns_options_and_slug():
    from thetatauCMT.regions.dashboard import sync_region_from_url

    options, slug = sync_region_from_url("/regions/national/")
    assert any(opt["value"] == "national" for opt in options)
    assert slug == "national"


@pytest.mark.django_db
def test_sync_region_from_url_falls_back_when_slug_unknown():
    from thetatauCMT.regions.dashboard import sync_region_from_url

    _, slug = sync_region_from_url("/regions/does-not-exist/")
    assert slug == "national"


def test_store_region_uses_national_as_fallback():
    from thetatauCMT.regions.dashboard import store_region

    assert store_region("", None) == "national"
    assert store_region(None, None) == "national"
    assert store_region("west", None) == "west"


def test_store_region_prefers_override():
    """A forced scope override wins over the region selector value."""
    from thetatauCMT.regions.dashboard import store_region

    assert store_region("national", "chapter_alpha") == "chapter_alpha"
    assert store_region("west", None) == "west"
    assert store_region(None, None) == "national"


@pytest.mark.django_db
def test_get_scope_chapters_single_chapter_scope():
    """A `chapter_<slug>` scope returns only that chapter."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.regions.dashboard import get_scope_chapters

    chapter = ChapterFactory()
    scoped = list(get_scope_chapters(f"chapter_{chapter.slug}"))
    assert [c.pk for c in scoped] == [chapter.pk]


@pytest.mark.django_db
def test_member_count_includes_pnms():
    """The 'member' KPI counts active members + PNMs together."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.regions.dashboard import MEMBER_STATUSES, update_kpis
    from thetatauCMT.regions.tests.factories import RegionFactory
    from thetatauCMT.users.tests.factories import UserFactory

    assert "pnm" in MEMBER_STATUSES

    region = RegionFactory(name="Member Count Region")
    chapter = ChapterFactory()
    chapter.region = region
    chapter.save(update_fields=["region"])
    UserFactory(chapter=chapter, current_status="active")
    UserFactory(chapter=chapter, current_status="pnm")

    # kpi-total-members is the first returned value; it must include the PNM.
    total_members = update_kpis(region.slug, None)[0]
    assert total_members == "2"


@pytest.mark.django_db
def test_living_census_counts_actives_and_alumni_excluding_deceased():
    """The living census counts actives + alumni, minus anyone marked deceased."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.regions.dashboard import update_kpis
    from thetatauCMT.regions.tests.factories import RegionFactory
    from thetatauCMT.users.tests.factories import UserFactory

    region = RegionFactory(name="Living Census Region")
    chapter = ChapterFactory()
    chapter.region = region
    chapter.save(update_fields=["region"])
    UserFactory(chapter=chapter, current_status="active")
    UserFactory(chapter=chapter, current_status="alumni")
    UserFactory(chapter=chapter, current_status="alumni", deceased=True)
    UserFactory(chapter=chapter, current_status="pnm")

    # kpi-living-census is the second returned value.
    assert update_kpis(region.slug, None)[1] == "2"


@pytest.mark.django_db
def test_living_census_includes_closed_chapters():
    """Alumni of a closed chapter are still living members of the fraternity."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.regions.dashboard import update_kpis
    from thetatauCMT.regions.tests.factories import RegionFactory
    from thetatauCMT.users.tests.factories import UserFactory

    region = RegionFactory(name="Closed Chapter Region")
    chapter = ChapterFactory()
    chapter.region = region
    chapter.active = False
    chapter.save(update_fields=["region", "active"])
    UserFactory(chapter=chapter, current_status="alumni")

    kpis = update_kpis(region.slug, None)
    assert kpis[1] == "1"
    # Every other KPI still ignores closed chapters.
    assert kpis[0] == "0"


@pytest.mark.django_db
def test_graduates_count_members_with_a_graduation_in_the_academic_year():
    """Graduates = members with a graduation report dated inside the AY, each counted once."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory
    from thetatauCMT.forms.tests.factories import StatusChangeFactory
    from thetatauCMT.regions.dashboard import graduates_by_chapter, update_kpis
    from thetatauCMT.regions.tests.factories import RegionFactory
    from thetatauCMT.users.tests.factories import UserFactory

    region = RegionFactory(name="Graduates Region")
    chapter = ChapterFactory()
    chapter.region = region
    chapter.save(update_fields=["region"])

    def report(reason, date_start, user=None):
        StatusChangeFactory(user=user or UserFactory(chapter=chapter), reason=reason, date_start=date_start)

    reported_twice = UserFactory(chapter=chapter)
    report("graduate", datetime.date(2025, 12, 13), user=reported_twice)
    report("graduate", datetime.date(2025, 12, 13), user=reported_twice)
    report("graduate", datetime.date(2026, 5, 9))
    # Outside AY 2025-26, or not a graduation.
    report("graduate", datetime.date(2025, 6, 30))
    report("graduate", datetime.date(2026, 7, 1))
    report("withdraw", datetime.date(2026, 1, 15))

    # kpi-graduates is the fifth returned value.
    assert update_kpis(region.slug, 2025)[4] == "2"
    fig = graduates_by_chapter(region.slug, 2025, "light")
    assert list(fig.data[0].y) == [2]


# ---------------------------------------------------------------------------
# Region pages: what a National Officer sees, and the chapter-level charts
# ---------------------------------------------------------------------------


@pytest.fixture
def view_as(db):
    """Serve callbacks to ``user``, as the dashboard's pages do."""
    from django.test import RequestFactory
    from django_userforeignkey.request import set_current_request

    def bind(user):
        request = RequestFactory().get("/")
        request.user = user
        set_current_request(request)
        return user

    yield bind
    set_current_request(None)


@pytest.fixture
def natoff_viewer(view_as):
    """A signed-in National Officer, as on the region pages."""
    from django.contrib.auth.models import Group

    from thetatauCMT.users.models import User
    from thetatauCMT.users.tests.factories import UserFactory

    user = UserFactory()
    Group.objects.get_or_create(name="natoff")[0].user_set.add(user)
    return view_as(User.objects.get(pk=user.pk))


def _region(name):
    from thetatauCMT.regions.tests.factories import RegionFactory

    return RegionFactory(name=name)


def _chapter(region, name=None, **fields):
    """A chapter in ``region``; pass a Greek ``name`` when a test needs two of them."""
    from thetatauCMT.chapters.tests.factories import ChapterFactory

    chapter = ChapterFactory(**({"name": name} if name else {}))
    chapter.region = region
    for field, value in fields.items():
        setattr(chapter, field, value)
    chapter.save()
    return chapter


def _member(chapter, **fields):
    from thetatauCMT.users.tests.factories import UserFactory

    return UserFactory(chapter=chapter, **fields)


def _senior_year():
    """The graduation year of this academic year's seniors."""
    from core.models import academic_encompass_start_end_date

    return academic_encompass_start_end_date()[1].year


@pytest.mark.django_db
def test_kpi_notes_compare_each_card_with_the_year_before(natoff_viewer):
    from thetatauCMT.forms.tests.factories import InitiationFactory
    from thetatauCMT.regions.dashboard import KPI_CARDS, update_kpis

    region = _region("KPI Notes Region")
    chapter = _chapter(region)
    for day in (datetime.date(2025, 10, 1), datetime.date(2026, 2, 1), datetime.date(2024, 10, 1)):
        InitiationFactory(user=_member(chapter), chapter=chapter, date=day)

    kpis = update_kpis(region.slug, 2025)
    notes = dict(zip((card_id for card_id, _, _ in KPI_CARDS), kpis[len(KPI_CARDS) :]))
    assert kpis[3] == "2"
    assert notes["kpi-initiations"] == "▲ 1 (100%) vs AY 2024–25"
    assert notes["kpi-graduates"] == "No change vs AY 2024–25"
    # No PNMs in either year, so there is no retention to compare.
    assert notes["kpi-retention"] == ""
    assert notes["kpi-total-members"].endswith("vs a year ago")
    # The member home page keeps its cards as they were.
    assert update_kpis(f"chapter_{chapter.slug}", 2025)[len(KPI_CARDS) :] == ("",) * len(KPI_CARDS)


@pytest.mark.parametrize(
    "today, graduation_year, standing",
    [
        (datetime.date(2026, 11, 1), 2031, "Freshman"),
        (datetime.date(2026, 11, 1), 2030, "Freshman"),
        (datetime.date(2026, 11, 1), 2029, "Sophomore"),
        (datetime.date(2026, 11, 1), 2028, "Junior"),
        (datetime.date(2026, 11, 1), 2027, "Senior"),
        # A December graduate.
        (datetime.date(2026, 11, 1), 2026, "Senior"),
        (datetime.date(2026, 11, 1), 2025, "5th year +"),
        (datetime.date(2027, 3, 1), 2027, "Senior"),
        (datetime.date(2027, 3, 1), 2026, "5th year +"),
    ],
)
def test_class_standing_counts_the_years_to_graduation(today, graduation_year, standing):
    from thetatauCMT.regions.dashboard import class_standing

    assert class_standing(graduation_year, today) == standing


@pytest.mark.django_db
def test_class_year_mix_counts_one_chapters_student_members_by_class():
    from thetatauCMT.regions.dashboard import CLASS_STANDINGS, class_year_mix

    chapter = _chapter(_region("Class Mix Region"))
    _member(chapter, current_status="active", graduation_year=_senior_year())
    _member(chapter, current_status="active", graduation_year=_senior_year() + 3)
    _member(chapter, current_status="pnm", graduation_year=_senior_year() + 3)
    _member(chapter, current_status="alumni", graduation_year=_senior_year() + 1)

    fig = class_year_mix(f"chapter_{chapter.slug}", "light")
    assert list(fig.data[0].x) == CLASS_STANDINGS
    assert list(fig.data[0].y) == [2, 0, 0, 1, 0]


@pytest.mark.django_db
def test_class_year_mix_puts_chapters_about_to_lose_the_most_members_first():
    from thetatauCMT.regions.dashboard import class_year_mix

    region = _region("Class Mix Rollup Region")
    young = _chapter(region, "alpha")
    old = _chapter(region, "beta")
    _member(young, current_status="active", graduation_year=_senior_year() + 3)
    _member(young, current_status="active", graduation_year=_senior_year())
    _member(old, current_status="active", graduation_year=_senior_year())

    fig = class_year_mix(region.slug, "light")
    seniors = next(trace for trace in fig.data if trace.name == "Senior")
    assert list(seniors.x) == [old.name, young.name]
    assert list(seniors.y) == [100.0, 50.0]
    # The legend sits above the bars, clear of the rotated chapter names.
    assert fig.layout.legend.y > 1


@pytest.mark.django_db
def test_gpa_shows_one_chapters_terms_and_rolls_up_by_chapter():
    from thetatauCMT.regions.dashboard import gpa_by_chapter
    from thetatauCMT.users.models import UserSemesterGPA

    region = _region("GPA Region")
    chapter = _chapter(region)
    first, second = _member(chapter), _member(chapter)
    for user, year, term, gpa in [
        (first, 2025, "fa", 3.0),
        (second, 2025, "fa", 4.0),
        (first, 2026, "sp", 3.2),
        # The next academic year.
        (first, 2026, "fa", 1.0),
    ]:
        UserSemesterGPA.objects.create(user=user, year=year, term=term, gpa=gpa)

    fig = gpa_by_chapter(f"chapter_{chapter.slug}", 2025, "light")
    assert list(fig.data[0].x) == ["Fall 2025", "Spring 2026"]
    assert [round(value, 2) for value in fig.data[0].y] == [3.5, 3.2]
    assert list(fig.data[0].customdata) == [2, 1]

    fig = gpa_by_chapter(region.slug, 2025, "light")
    assert list(fig.data[0].y) == [3.4]
    assert fig.layout.shapes[0].y0 == pytest.approx(3.4)


@pytest.mark.django_db
def test_service_hours_show_one_chapters_terms_and_the_average_chapter():
    from thetatauCMT.regions.dashboard import service_hours_by_chapter
    from thetatauCMT.users.models import UserSemesterServiceHours

    region = _region("Service Region")
    alpha = _chapter(region, "alpha")
    beta = _chapter(region, "beta")
    for user, year, term, hours in [
        (_member(alpha), 2025, "fa", 10),
        (_member(alpha), 2026, "sp", 20),
        (_member(beta), 2026, "sp", 6),
    ]:
        UserSemesterServiceHours.objects.create(user=user, year=year, term=term, service_hours=hours)

    fig = service_hours_by_chapter(f"chapter_{alpha.slug}", 2025, "light")
    assert list(fig.data[0].x) == ["Fall 2025", "Spring 2026"]
    assert list(fig.data[0].y) == [10, 20]

    fig = service_hours_by_chapter(region.slug, 2025, "light")
    assert {name: hours for trace in fig.data for name, hours in zip(trace.x, trace.y)} == {"alpha": 30, "beta": 6}
    assert fig.layout.shapes[0].y0 == pytest.approx(18)


@pytest.mark.django_db
def test_funds_raised_show_one_chapters_terms_and_the_average_chapter():
    from thetatauCMT.events.tests.factories import EventFactory
    from thetatauCMT.regions.dashboard import funds_raised_by_chapter
    from thetatauCMT.scores.models import ScoreType

    region = _region("Funds Region")
    alpha = _chapter(region, "alpha")
    beta = _chapter(region, "beta")
    project = ScoreType.objects.get(slug="service-project")
    for chapter, day, raised in [
        (alpha, datetime.date(2025, 10, 1), 100),
        (alpha, datetime.date(2025, 11, 1), 50),
        (alpha, datetime.date(2026, 3, 1), 25),
        (alpha, datetime.date(2026, 4, 1), 0),
        # The next academic year.
        (alpha, datetime.date(2026, 9, 1), 500),
        (beta, datetime.date(2026, 2, 1), 75),
    ]:
        EventFactory(chapter=chapter, type=project, date=day, raised=Decimal(raised))

    fig = funds_raised_by_chapter(f"chapter_{alpha.slug}", 2025, "light")
    assert list(fig.data[0].x) == ["Fall 2025", "Spring 2026"]
    assert list(fig.data[0].y) == [150, 25]
    assert list(fig.data[0].customdata) == [2, 1]

    fig = funds_raised_by_chapter(region.slug, 2025, "light")
    assert {name: raised for trace in fig.data for name, raised in zip(trace.x, trace.y)} == {"alpha": 175, "beta": 75}
    assert fig.layout.shapes[0].y0 == pytest.approx(125)
    assert fig.layout.annotations[0].text == "Average chapter $125, total $250"


@pytest.mark.django_db
def test_events_and_submissions_by_category_count_each_score_type():
    from thetatauCMT.events.tests.factories import EventFactory
    from thetatauCMT.regions import dashboard as d
    from thetatauCMT.scores.models import ScoreType
    from thetatauCMT.submissions.tests.factories import SubmissionFactory

    region = _region("Category Region")
    chapter = _chapter(region)
    in_year, next_year = datetime.date(2025, 10, 1), datetime.date(2026, 9, 1)
    for slug, day in [
        ("brotherhood", in_year),
        ("brotherhood", in_year + datetime.timedelta(days=1)),
        ("meetings", in_year),
        ("meetings", next_year),
    ]:
        EventFactory(chapter=chapter, type=ScoreType.objects.get(slug=slug), date=day)
    for slug, day in [("audit", in_year), ("osm", in_year), ("osm", next_year)]:
        SubmissionFactory(chapter=chapter, type=ScoreType.objects.get(slug=slug), date=day)

    events = d.events_by_category(region.slug, 2025, "light")
    assert {trace.name: dict(zip(trace.y, trace.x)) for trace in events.data} == {
        "Brotherhood": {"Brotherhood activities": 2},
        "Operate": {"Attendance at meetings": 1},
    }
    assert list(events.layout.yaxis.categoryarray) == ["Brotherhood activities", "Attendance at meetings"]
    submissions = d.submissions_by_category(f"chapter_{chapter.slug}", 2025, "light")
    assert {trace.name: dict(zip(trace.y, trace.x)) for trace in submissions.data} == {
        "Operate": {"Financial Audits": 1, "Outstanding Student Member Program": 1},
    }


@pytest.mark.django_db
def test_membership_changes_count_who_joined_stepped_away_and_left():
    from viewflow.activation import STATUS

    from thetatauCMT.forms.flows import ResignationFlow, ReturnStudentFlow
    from thetatauCMT.forms.models import ResignationProcess, ReturnStudent
    from thetatauCMT.forms.tests.factories import (
        DepledgeFactory,
        InitiationFactory,
        PrematureAlumnusFactory,
        StatusChangeFactory,
    )
    from thetatauCMT.regions import dashboard as d
    from thetatauCMT.users.models import UserStatusChange

    region = _region("Changes Region")
    chapter = _chapter(region)
    in_year, next_year = datetime.date(2025, 10, 1), datetime.date(2026, 9, 1)
    approved = timezone.make_aware(datetime.datetime(2026, 2, 1))

    UserStatusChange.objects.create(user=_member(chapter), status="pnm", start=in_year, end=datetime.date(2100, 1, 1))
    InitiationFactory(user=_member(chapter), chapter=chapter, date=in_year)
    DepledgeFactory(user=_member(chapter), date=in_year)
    for reason in ("graduate", "coop", "coop", "military", "withdraw", "transfer", "resignedCC"):
        StatusChangeFactory(user=_member(chapter), reason=reason, date_start=in_year)
    StatusChangeFactory(user=_member(chapter), reason="coop", date_start=next_year)
    PrematureAlumnusFactory(user=_member(chapter), approved_exec=True, status=STATUS.DONE, finished=approved)
    PrematureAlumnusFactory(user=_member(chapter), approved_exec=False, status=STATUS.DONE, finished=approved)
    resigning = _member(chapter)
    ResignationProcess.objects.create(
        flow_class=ResignationFlow,
        user=resigning,
        chapter=chapter,
        officer1=resigning,
        officer2=resigning,
        approved_exec=True,
        finished=approved,
    )
    ReturnStudent.objects.create(
        flow_class=ReturnStudentFlow,
        user=_member(chapter),
        reason="Back from co-op",
        approved_exec=True,
        finished=approved,
    )

    fig = d.membership_changes(region.slug, 2025, "light")
    assert {trace.name: dict(zip(trace.y, trace.x)) for trace in fig.data} == {
        "Joined or returned": {"New PNMs": 1, "Initiated": 1, "Returned to student status": 1},
        "Away for a time": {"Co-op or study abroad": 2, "Military deployment": 1},
        "Left": {
            "Graduated": 1,
            "Premature alumni": 1,
            "Withdrew from school": 1,
            "Transferred": 1,
            # A resignation form, and a candidate chapter member's status change.
            "Resigned": 2,
            "Depledged": 1,
        },
    }


@pytest.mark.django_db
def test_gpa_mix_puts_chapters_with_the_most_members_at_risk_first(natoff_viewer, view_as):
    from thetatauCMT.regions import dashboard as d
    from thetatauCMT.users.models import UserSemesterGPA

    region = _region("GPA Mix Region")
    alpha = _chapter(region, "alpha")
    beta = _chapter(region, "beta")
    struggling, strong, steady = _member(alpha), _member(alpha), _member(beta)
    for user, year, term, gpa in [
        # Averages 2.2 over the year.
        (struggling, 2025, "fa", 1.9),
        (struggling, 2026, "sp", 2.5),
        (strong, 2025, "fa", 3.8),
        (steady, 2026, "sp", 3.2),
        # The next academic year.
        (steady, 2026, "fa", 1.0),
    ]:
        UserSemesterGPA.objects.create(user=user, year=year, term=term, gpa=gpa)

    fig = d.gpa_mix(region.slug, 2025, "light")
    shares = {trace.name: dict(zip(trace.x, trace.y)) for trace in fig.data}
    assert list(fig.data[0].x) == ["alpha", "beta"]
    assert shares["2.0 to 2.49"] == {"alpha": 50.0, "beta": 0.0}
    assert shares["3.0 to 3.49"] == {"alpha": 0.0, "beta": 100.0}
    assert shares["3.5 and up"] == {"alpha": 50.0, "beta": 0.0}
    # Not on the member home page, and nothing for a member who asks for a region.
    assert len(d.gpa_mix(f"chapter_{alpha.slug}", 2025, "light").data) == 0
    view_as(_member(alpha, current_status="active"))
    assert len(d.gpa_mix(region.slug, 2025, "light").data) == 0


@pytest.mark.parametrize(
    "gpa, band",
    [(1.99, "Below 2.0"), (2.0, "2.0 to 2.49"), (2.49, "2.0 to 2.49"), (3.0, "3.0 to 3.49"), (4.0, "3.5 and up")],
)
def test_gpa_band_starts_each_band_at_its_floor(gpa, band):
    from thetatauCMT.regions.dashboard import gpa_band

    assert gpa_band(gpa) == band


@pytest.mark.django_db
def test_top_societies_rank_professional_and_technical_organizations():
    from thetatauCMT.regions import dashboard as d
    from thetatauCMT.users.tests.factories import OrganizationFactory, UserOrgParticipateFactory

    region = _region("Societies Region")
    chapter = _chapter(region)
    ieee, swe, honor = (OrganizationFactory(name=name) for name in ("IEEE", "SWE", "Tau Beta Pi"))
    in_year = {"start": datetime.date(2025, 9, 1), "end": datetime.date(2026, 5, 1)}
    for organization, kind in [(ieee, "tec"), (ieee, "pro"), (swe, "pro"), (honor, "hon")]:
        UserOrgParticipateFactory(organization=organization, type=kind, user=_member(chapter), **in_year)
    # Ended before the academic year began.
    UserOrgParticipateFactory(
        organization=swe,
        type="pro",
        user=_member(chapter),
        start=datetime.date(2024, 9, 1),
        end=datetime.date(2025, 5, 1),
    )

    fig = d.top_societies(region.slug, 2025, "light")
    # Largest on top: plotly draws the first bar at the bottom.
    assert list(fig.data[0].y) == ["SWE", "IEEE"]
    assert list(fig.data[0].x) == [1, 2]


@pytest.mark.django_db
def test_region_panels_need_a_national_officer_on_a_region_page(natoff_viewer, view_as):
    from thetatauCMT.regions import dashboard as d

    region = _region("Gated Region")
    chapter = _chapter(region)
    _member(chapter, current_status="active", last_login=timezone.now())

    assert d.chapter_health(region.slug, None)[-1] is not None
    assert len(d.cmt_use_by_chapter(region.slug, "light").data) == 2
    # The home page and a CSS's landing page fix the scope, even for a National Officer.
    assert d.chapter_health(f"chapter_{chapter.slug}", None)[-1] is None
    assert d.chapter_health(d.SUPPORT_SCOPE, None)[-1] is None

    # The browser names the scope, so a member asking for a region gets nothing.
    view_as(_member(chapter, current_status="active"))
    assert d.chapter_health(region.slug, None)[-1] is None
    assert len(d.cmt_use_by_chapter(region.slug, "light").data) == 0
    assert len(d.membership_trends(region.slug, "light").data) == 0


@pytest.mark.django_db
def test_a_css_sees_notes_trends_and_cmt_use_for_their_own_chapters(view_as):
    from thetatauCMT.regions import dashboard as d
    from thetatauCMT.support.tests.factories import ChapterSupportAssignmentFactory, make_css
    from thetatauCMT.users.models import User

    region = _region("CSS Region")
    mine = _chapter(region, "alpha")
    other = _chapter(region, "beta")
    for chapter in (mine, other):
        _member(chapter, current_status="active", last_login=timezone.now())
    css = make_css()
    ChapterSupportAssignmentFactory(user=css, chapter=mine)
    view_as(User.objects.get(pk=css.pk))
    first_note = len(d.KPI_CARDS)

    kpis = d.update_kpis(d.SUPPORT_SCOPE, None)
    assert kpis[0] == "1"
    assert kpis[first_note].endswith("vs a year ago")
    assert d.update_kpis(f"chapter_{mine.slug}", None)[first_note].endswith("vs a year ago")
    cmt_use = d.cmt_use_by_chapter(d.SUPPORT_SCOPE, "light")
    assert {name for trace in cmt_use.data for name in trace.x} == {mine.name}
    assert len(d.membership_trends(d.SUPPORT_SCOPE, "light").data) == 3
    # The rest stays on the region pages.
    assert d.chapter_health(d.SUPPORT_SCOPE, None)[-1] is None
    assert len(d.alumni_reach(d.SUPPORT_SCOPE, "light").data) == 0
    assert len(d.programs_by_year(d.SUPPORT_SCOPE, "light").data) == 0
    # Nothing for a chapter they do not support, whatever the browser asks for.
    assert d.update_kpis(f"chapter_{other.slug}", None)[first_note] == ""
    assert len(d.cmt_use_by_chapter(f"chapter_{other.slug}", "light").data) == 0


def test_extra_panels_show_on_the_region_pages_and_partly_on_a_css_landing_page():
    from thetatauCMT.regions.dashboard import REGION_AND_CSS_IDS, REGION_ONLY_IDS, toggle_region_only

    shown, hidden = {}, {"display": "none"}
    region_only, region_and_css = len(REGION_ONLY_IDS), len(REGION_AND_CSS_IDS)
    assert toggle_region_only(None) == [shown] * (region_only + region_and_css)
    assert toggle_region_only("support") == [hidden] * region_only + [shown] * region_and_css
    assert toggle_region_only("chapter_alpha") == [hidden] * (region_only + region_and_css)


@pytest.mark.django_db
def test_chapter_health_rolls_up_size_tasks_balance_seats_reports_and_ballots(natoff_viewer):
    from core.models import academic_encompass_start_end_date
    from thetatauCMT.ballots.models import Ballot, BallotComplete
    from thetatauCMT.chapters.models import MIN_CHAPTER_SIZE_CONFIG_KEY
    from thetatauCMT.configs.models import Config
    from thetatauCMT.regions import dashboard as d
    from thetatauCMT.transitions.models import ReportObligation

    Config.objects.create(key=MIN_CHAPTER_SIZE_CONFIG_KEY, value="2", description="")
    region = _region("Health Region")
    small = _chapter(region, "alpha", balance=Decimal("125.25"))
    large = _chapter(region, "beta", balance=Decimal("-20"))
    _member(small, current_status="active")
    regent = _member(large, current_status="active", current_roles=["regent"])
    _member(large, current_status="active")
    _member(large, current_status="pnm")

    # Last academic year, so its ballots have closed.
    ay = academic_encompass_start_end_date()[0].year - 1
    for position_key, status in (("regent", "submitted"), ("scribe", "open")):
        ReportObligation.objects.create(
            chapter=small,
            position_type="CHAPTER_OFFICER",
            position_key=position_key,
            term_start=datetime.date(ay, 7, 1),
            term_end=datetime.date(ay + 1, 5, 1),
            due_date=datetime.date(ay + 1, 4, 17),
            status=status,
        )
    ballots = [
        Ballot.objects.create(
            name=f"Health ballot {n}", type="other", description="Vote", due_date=due, voters=["all_chapters"]
        )
        for n, due in enumerate((datetime.date(ay, 10, 1), datetime.date(ay + 1, 3, 1)))
    ]
    BallotComplete.objects.create(user=regent, ballot=ballots[0], motion="aye", role="regent")

    rows = d.chapter_health_rows(d.get_scope_chapters(region.slug), ay)
    assert [row["chapter"].pk for row in rows] == [small.pk, large.pk]
    by_chapter = {row["chapter"].pk: row for row in rows}
    assert by_chapter[small.pk]["members"] == 1
    assert by_chapter[large.pk]["members"] == 3
    assert by_chapter[small.pk]["missing"] == [
        "Regent",
        "Scribe",
        "Vice Regent",
        "Treasurer",
        "Corresponding Secretary",
    ]
    assert "Regent" not in by_chapter[large.pk]["missing"]
    assert (by_chapter[small.pk]["reports_submitted"], by_chapter[small.pk]["reports_due"]) == (1, 2)
    assert (by_chapter[large.pk]["ballots_voted"], by_chapter[large.pk]["ballots_eligible"]) == (1, 2)
    assert (by_chapter[small.pk]["ballots_voted"], by_chapter[small.pk]["ballots_eligible"]) == (0, 2)

    cards = d.chapter_health(region.slug, ay)
    overdue = str(sum(bool(row["overdue"]) for row in rows))
    assert cards[:6] == ["1", overdue, "$125", "9", "50%", "25%"]
    assert cards[6] == "fewer than 2 student members"
    first_row = cards[7].children[2].children[0]
    assert first_row.children[2].children[1].children == "Below 2"


@pytest.mark.django_db
def test_chapter_counts_split_active_candidate_and_closed_chapters(natoff_viewer):
    from thetatauCMT.regions import dashboard as d

    region = _region("Counts Region")
    _chapter(region, "alpha", recognition="fraternity", school_type="semester")
    _chapter(region, "beta", candidate_chapter=True, recognition="org", school_type="quarter")
    _chapter(region, "delta", active=False)

    values = d.chapter_counts(region.slug, "light")
    assert values[:3] == ["1", "1", "1"]
    assert dict(zip(values[3].data[0].y, values[3].data[0].x)) == {
        "Recognized as a Fraternity": 1,
        "Recognized as a Student Organization NOT a Fraternity": 1,
    }
    assert dict(zip(values[4].data[0].y, values[4].data[0].x)) == {"Semester": 1, "Quarter": 1}


@pytest.mark.django_db
def test_membership_trends_count_each_academic_year(natoff_viewer):
    from core.models import academic_encompass_start_end_date
    from thetatauCMT.forms.tests.factories import InitiationFactory, StatusChangeFactory
    from thetatauCMT.regions import dashboard as d
    from thetatauCMT.users.models import UserStatusChange

    region = _region("Trends Region")
    chapter = _chapter(region, "alpha")
    elsewhere = _chapter(_region("Elsewhere Region"), "beta")
    current = academic_encompass_start_end_date()[0].year
    UserStatusChange.objects.create(
        user=_member(chapter),
        status="active",
        start=timezone.localdate() - datetime.timedelta(days=800),
        end=datetime.date(2100, 1, 1),
    )
    # Initiated by this chapter, a member of another one now.
    InitiationFactory(user=_member(elsewhere), chapter=chapter, date=datetime.date(current - 1, 10, 1))
    StatusChangeFactory(user=_member(chapter), reason="graduate", date_start=datetime.date(current, 1, 15))

    initiations, graduates, members = d.membership_trends(region.slug, "light").data
    assert list(initiations.y) == [0, 0, 0, 1, 0]
    assert list(graduates.y) == [0, 0, 0, 1, 0]
    assert list(members.y) == [0, 0, 1, 1, 1]
    assert initiations.x[-1].endswith("(to date)")


@pytest.mark.django_db
def test_programs_by_year_count_awards_job_postings_and_nominations(natoff_viewer):
    from thetatauCMT.awards.tests.factories import AwardGrantFactory
    from thetatauCMT.jobs.models import Job
    from thetatauCMT.nominations.tests.factories import NominationFactory
    from thetatauCMT.regions import dashboard as d

    region = _region("Programs Region")
    member = _member(_chapter(region, "alpha"))
    AwardGrantFactory(recipient_member=member)
    job = Job.objects.create(
        company="Acme",
        description="Build things",
        education_qualification=["bachelors"],
        experience=["new_grad"],
        job_type=["full_time"],
        location_type=["remote"],
        title="Engineer",
        url="https://example.com/job",
    )
    # created_by fills from the signed-in viewer on save.
    Job.objects.filter(pk=job.pk).update(created_by=member)
    NominationFactory(nominee=member)

    fig = d.programs_by_year(region.slug, "light")
    assert {trace.name: list(trace.y) for trace in fig.data} == {
        "Awards granted": [0, 0, 0, 0, 1],
        "Job postings": [0, 0, 0, 0, 1],
        "Volunteer nominations": [0, 0, 0, 0, 1],
    }


@pytest.mark.django_db
def test_alumni_reach_counts_who_can_be_reached_by_email_and_mail(natoff_viewer):
    from thetatauCMT.email_tracking.models import TrackedEmail
    from thetatauCMT.regions import dashboard as d

    region = _region("Reach Region")
    chapter = _chapter(region, "alpha")
    now = timezone.now()
    reachable = _member(chapter, current_status="alumni")
    _member(chapter, current_status="alumni", no_contact=True)
    _member(chapter, current_status="alumni", unsubscribe_email=True, address=None)
    bouncing = _member(chapter, current_status="alumni")
    _member(chapter, current_status="alumni", deceased=True)
    _member(chapter, current_status="active")
    # An old bounce stops counting once a later message gets through.
    month_ago = now - datetime.timedelta(days=30)
    TrackedEmail.objects.create(
        message_id="old", recipient=reachable.email, user=reachable, sent_at=month_ago, bounced_at=month_ago
    )
    TrackedEmail.objects.create(
        message_id="new", recipient=reachable.email, user=reachable, sent_at=now, delivered_at=now
    )
    TrackedEmail.objects.create(
        message_id="bounce", recipient=bouncing.email, user=bouncing, sent_at=now, bounced_at=now
    )

    fig = d.alumni_reach(region.slug, "light")
    assert dict(zip(fig.data[0].y, fig.data[0].x)) == {
        "Living alumni": 4,
        "Open to contact": 3,
        "Reachable by email": 1,
        "Reachable by mail": 2,
    }


@pytest.mark.django_db
def test_cmt_use_compares_officers_with_the_other_student_members(natoff_viewer):
    from thetatauCMT.regions import dashboard as d

    region = _region("CMT Use Region")
    alpha = _chapter(region, "alpha")
    beta = _chapter(region, "beta")
    recently = timezone.now() - datetime.timedelta(days=10)
    long_ago = timezone.now() - datetime.timedelta(days=200)
    _member(alpha, current_status="active", current_roles=["regent"], last_login=recently)
    _member(alpha, current_status="active", current_roles=["treasurer"], last_login=long_ago)
    # A committee chair has no officer access, so counts with the other members.
    _member(alpha, current_status="active", current_roles=["events chair"], last_login=recently)
    _member(alpha, current_status="active", last_login=recently)
    _member(alpha, current_status="pnm", last_login=long_ago)
    _member(alpha, current_status="active", last_login=None)
    _member(alpha, current_status="active", last_login=None)
    _member(alpha, current_status="alumni", current_roles=["regent"], last_login=recently)
    _member(beta, current_status="active", last_login=recently)

    officers, others = d.cmt_use_by_chapter(region.slug, "light").data
    assert list(officers.x) == list(others.x) == ["alpha", "beta"]
    assert list(officers.y) == [50, None]
    assert list(others.y) == [40, 100]
    assert officers.name == "Officers (50% overall)"
    assert others.name == "Other members (50% overall)"


@pytest.mark.django_db
def test_placement_and_degrees_describe_the_years_graduates(natoff_viewer):
    from thetatauCMT.forms.tests.factories import EmployerFactory, StatusChangeFactory
    from thetatauCMT.regions import dashboard as d

    region = _region("Placement Region")
    chapter = _chapter(region, "alpha")
    StatusChangeFactory(
        user=_member(chapter),
        reason="graduate",
        degree="bs",
        date_start=datetime.date(2025, 12, 13),
        employer=EmployerFactory(),
    )
    StatusChangeFactory(
        user=_member(chapter), reason="graduate", degree="ms", date_start=datetime.date(2026, 5, 9), employer=None
    )

    fig = d.placement_by_chapter(region.slug, 2025, "light")
    assert list(fig.data[0].y) == [50]
    assert fig.layout.shapes[0].y0 == pytest.approx(50)
    fig = d.graduates_by_degree(region.slug, 2025, "light")
    assert dict(zip(fig.data[0].y, fig.data[0].x)) == {"Bachelor of Science": 1, "Master of Science": 1}
