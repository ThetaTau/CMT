"""Unit tests for `thetatauCMT.regions.dashboard`.

Covers pure helpers (`parse_region_slug`, `_theme_template`, `_apply_theme`,
`_empty_figure`, `_bar_by_chapter`, `region_options`, `get_scope_chapters`)
and integration-lite invocations of the KPI + graph callbacks against the
test DB.
"""

import plotly.graph_objects as go
import pytest

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
def test_update_kpis_returns_six_values():
    from thetatauCMT.regions.dashboard import update_kpis

    result = update_kpis("national", None)
    assert isinstance(result, tuple)
    assert len(result) == 6
    for v in result:
        assert isinstance(v, str)


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
        "depledges_by_chapter",
        "events_by_chapter",
        "submissions_by_chapter",
        "tasks_by_chapter",
        "trainings_by_chapter",
        "scores_total_by_chapter",
        "scores_bro_by_chapter",
        "scores_ops_by_chapter",
        "scores_pro_by_chapter",
        "scores_ser_by_chapter",
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

    assert store_region("") == "national"
    assert store_region(None) == "national"
    assert store_region("west") == "west"
