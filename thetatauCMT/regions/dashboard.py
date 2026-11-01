"""Regional / National dashboard rendered via django-plotly-dash.

The same `RegionDashboard` app powers both `/regions/national/` (all chapters)
and `/regions/<slug>/` (chapters in one region). The active region is inferred
from the browser URL via `dcc.Location`; national officers can override the
scope with the region dropdown at the top of the layout.
"""

import datetime
from collections import defaultdict

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dcc, html
from django.conf import settings
from django.db.models import Avg, Count, OuterRef, Q, Subquery, Sum
from django.urls import reverse
from django.utils import timezone
from django_plotly_dash import DjangoDash
from django_userforeignkey.request import get_current_user

from core.models import (
    ALUMNI_STATUSES,
    CHAPTER_OFFICER,
    YearTermModel,
    academic_encompass_start_end_date,
    user_is_national_officer,
)
from thetatauCMT.chapters.models import Chapter, min_chapter_size
from thetatauCMT.regions.models import Region
from thetatauCMT.support.services import css_dashboard_chapter_ids, css_state

# `serve_locally=False` tells dash-renderer to load plotly.min.js from the
# Plotly CDN instead of an internal `_dash-component-suites/...` URL.
# django-plotly-dash 2.5.1 doesn't route the new URL scheme dash 3+/4
# generates for locally-served assets, so the client 404s and dash-renderer
# unmounts every `dcc.Graph` (leaving empty card-body divs).
# `external_scripts` guarantees plotly.min.js is fetched even if dash-renderer's
# own CDN lookup fails. Version pinned to what `plotly==6.8.0` ships bundled
# (see `plotly/package_data/plotly.min.js` — v3.6.0).
app = DjangoDash(
    "RegionDashboard",
    serve_locally=False,
    external_scripts=["https://cdn.plot.ly/plotly-3.6.0.min.js"],
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTIVE_STATUSES = ["active", "activepend", "alumnipend", "activeCC", "pendexpul"]

# The "member" count shown on member-facing charts includes PNMs (prospective
# new members) per org preference: the headline member metric = active members
# + PNMs. Use this (not ACTIVE_STATUSES) anywhere a chart reports "members".
MEMBER_STATUSES = ACTIVE_STATUSES + ["pnm"]

# Statuses whose members still count as "ours" for career charts. Alumni are
# the ones most likely to have an employer on file, so they are included here
# even though they are off the chapter roster.
CAREER_STATUSES = ACTIVE_STATUSES + ["alumni", "alumniCC", "advisor"]

# The "living census": actives + alumni who are not marked deceased. Unlike the
# other KPIs this is a standing head count, not scoped to the academic year.
CENSUS_STATUSES = ACTIVE_STATUSES + ALUMNI_STATUSES

# Distinct qualitative palette; falls back to Plotly D3 for extra regions.
REGION_PALETTE = px.colors.qualitative.Bold + px.colors.qualitative.D3

# The scope of a Chapter Support Specialist's landing page: their assigned chapters.
SUPPORT_SCOPE = "support"

# Class standing from the expected graduation year, youngest first.
CLASS_STANDINGS = ["Freshman", "Sophomore", "Junior", "Senior", "5th year +"]
CLASS_STANDING_COLORS = px.colors.qualitative.Safe

# A sign-in within this many days counts as using CMT.
CMT_USE_DAYS = 90


def _theme_template(theme):
    return "plotly_dark" if theme == "dark" else "plotly_white"


def _apply_theme(fig, theme):
    fig.update_layout(
        template=_theme_template(theme),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=20, t=60, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
    )
    return fig


def _empty_figure(theme, message="No data available"):
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    return _apply_theme(fig, theme)


def parse_region_slug(pathname):
    """Parse the region slug from a URL path like `/regions/<slug>/...`.

    Returns `"national"` when the URL is missing or malformed so that an
    unauthenticated / direct visit gets a sensible default rather than an
    error state.
    """
    if not pathname:
        return "national"
    parts = [p for p in pathname.strip("/").split("/") if p]
    if len(parts) >= 2 and parts[0] == "regions":
        return parts[1]
    return "national"


def get_scope_chapters(region_slug, include_inactive=False):
    """Return the queryset of active chapters in scope for `region_slug`.

    * `national` — all active chapters
    * `candidate_chapter` — all active candidate chapters
    * `chapter_<slug>` — the single chapter with that slug (member home page)
    * `support` — a Chapter Support Specialist's assigned chapters (their landing page)
    * any other slug — chapters whose region slug matches

    Pass `include_inactive=True` to keep closed chapters in scope; the living
    census counts their alumni, every other KPI is about current activity.

    The scope comes from the browser, so a Chapter Support Specialist is held to their
    own chapters here, on the server, whatever scope a request names.
    """
    qs = Chapter.objects.select_related("region")
    if not include_inactive:
        qs = qs.exclude(active=False)
    viewer = _signed_in_viewer()
    limit = css_dashboard_chapter_ids(viewer) if viewer is not None else None
    if limit is not None:
        qs = qs.filter(pk__in=limit)
    if region_slug == SUPPORT_SCOPE:
        if limit is None:
            return qs.none()
        return qs.filter(pk__in=css_state(viewer).chapter_ids)
    if region_slug == "national" or not region_slug:
        return qs
    if region_slug == "candidate_chapter":
        return qs.filter(candidate_chapter=True)
    if region_slug.startswith("chapter_"):
        return qs.filter(slug=region_slug[len("chapter_") :])
    return qs.filter(region__slug=region_slug)


def _signed_in_viewer():
    """The user of the request being served, when there is a signed-in one."""
    user = get_current_user()
    return user if getattr(user, "is_authenticated", False) else None


def _is_chapter_scope(region_slug):
    """One chapter: the member home page, or a single chapter picked on a CSS landing page."""
    return bool(region_slug) and region_slug.startswith("chapter_")


def _region_view(region_slug):
    """Whether the region and national panels apply: a region page, seen by a National Officer."""
    if _is_chapter_scope(region_slug) or region_slug == SUPPORT_SCOPE:
        return False
    return user_is_national_officer(_signed_in_viewer())


def _css_view(region_slug):
    """A Chapter Support Specialist on their landing page: all their chapters, or one of them."""
    viewer = _signed_in_viewer()
    if viewer is None or css_dashboard_chapter_ids(viewer) is None:
        return False
    if region_slug == SUPPORT_SCOPE:
        return True
    return (
        _is_chapter_scope(region_slug)
        and get_scope_chapters(SUPPORT_SCOPE).filter(slug=region_slug[len("chapter_") :]).exists()
    )


def _region_or_css_view(region_slug):
    """What a CSS shares with the region pages: year-over-year notes, trends and CMT use."""
    return _region_view(region_slug) or _css_view(region_slug)


def region_options():
    """Return dropdown options for the region selector."""
    return [{"label": name, "value": slug} for slug, name in Region.region_choices()]


def ay_options(years_back=5):
    """Return dropdown options for the academic-year selector, newest first."""
    current_start = academic_encompass_start_end_date()[0].year
    return [{"label": _ay_label(y), "value": y} for y in range(current_start, current_start - years_back, -1)]


def _ay_label(start_year):
    return f"AY {start_year}–{str(start_year + 1)[-2:]}"


def ay_dates(ay_start_year):
    """Return (start, end) `datetime` objects for the AY starting `ay_start_year`."""
    if ay_start_year is None:
        ay_start_year = academic_encompass_start_end_date()[0].year
    start = datetime.datetime(int(ay_start_year), 7, 1)
    end = datetime.datetime(int(ay_start_year) + 1, 7, 1)
    if getattr(settings, "USE_TZ", False):
        start = timezone.make_aware(start)
        end = timezone.make_aware(end)
    return start, end


def _ay_start(ay_start_year):
    """The selected academic year's start year, the current one when none is selected."""
    if ay_start_year is None:
        return academic_encompass_start_end_date()[0].year
    return int(ay_start_year)


def _ay_terms(ay_start_year):
    """A `YearTermModel` filter for an academic year: its Fall is `ay`, its Spring `ay + 1`."""
    ay = _ay_start(ay_start_year)
    return Q(year=ay, term="fa") | Q(year=ay + 1, term="sp")


def _recent_years():
    """The academic-year selector's years, oldest first."""
    return sorted(option["value"] for option in ay_options())


def _on_year(day, year):
    """`day` moved to `year`; Feb 29 becomes Feb 28."""
    try:
        return day.replace(year=year)
    except ValueError:
        return day.replace(year=year, day=28)


def class_standing(graduation_year, today):
    """Freshman to Senior from the expected graduation year, or "5th year +" once it has passed."""
    years_left = graduation_year - academic_encompass_start_end_date(today)[1].year
    # In the fall term, a graduation year equal to the calendar year is a December graduate.
    if years_left < 0 and graduation_year >= today.year:
        years_left = 0
    if years_left < 0:
        return CLASS_STANDINGS[-1]
    return CLASS_STANDINGS[max(0, 3 - years_left)]


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _kpi_card(card_id, label, subtitle="", note=False):
    # `col-xl` (no number) splits the row evenly however many cards it holds.
    return html.Div(
        className="col-6 col-md-4 col-xl mb-3",
        children=html.Div(
            className="card h-100 shadow-sm bg-body-tertiary text-body border-0",
            children=html.Div(
                className="card-body text-center",
                children=[
                    html.Div(label, className="card-subtitle text-body-secondary text-uppercase small mb-2"),
                    html.Div(id=card_id, className="card-title h3 fw-bold mb-1", children="0"),
                    html.Div(subtitle, className="text-body-secondary small") if subtitle else None,
                    html.Div(id=f"{card_id}-note", className="text-body-secondary small mt-1") if note else None,
                ],
            ),
        ),
    )


def _panel(title, graph_id, sm_cols=12, md_cols=12):
    # NOTE: do NOT wrap `dcc.Graph` in `dcc.Loading` here — in dash 4.x the
    # Loading component's children-normalisation drops nested Dash components
    # (see empty `card-body` in the rendered HTML). Dash 4 shows loading state
    # on the target output automatically, so this wrapper is redundant anyway.
    return html.Div(
        className=f"col-{sm_cols} col-md-{md_cols} mb-3",
        children=html.Div(
            className="card shadow-sm bg-body-tertiary text-body border-0 h-100",
            children=[
                html.Div(title, className="card-header bg-transparent border-0 fw-semibold"),
                html.Div(
                    className="card-body",
                    children=dcc.Graph(id=graph_id, config={"displaylogo": False}),
                ),
            ],
        ),
    )


# (id, label, subtitle) for the number cards. On the region pages each main card also
# carries a note comparing it with the year before.
KPI_CARDS = [
    ("kpi-total-members", "Student members today", "active + activepend + PNMs"),
    ("kpi-living-census", "Living census", "actives + alumni, not deceased"),
    ("kpi-pnms", "PNMs", "prospective status started"),
    ("kpi-initiations", "Initiations", "date within academic year"),
    ("kpi-graduates", "Graduates", "graduation date within academic year"),
    ("kpi-prealums", "Prealumni", "approved by exec"),
    ("kpi-resignations", "Resignations", "approved by exec"),
    ("kpi-retention", "PNM retention", "1 − depledges / PNMs"),
    ("kpi-communityedu", "Vector/CommunityEdu completion", "prior-year new members trained"),
]
CHAPTER_COUNT_CARDS = [
    ("count-chapters", "Chapters", "active"),
    ("count-candidate-chapters", "Candidate chapters", "active"),
    ("count-closed-chapters", "Closed chapters", "marked inactive"),
]
# The minimum-size card's note names the configured minimum.
HEALTH_CARDS = [
    ("health-below-minimum", "Below minimum size", ""),
    ("health-overdue", "Overdue tasks", "chapters behind in the last 90 days"),
    ("health-balance", "Balance owed", "sum of chapter balances"),
    ("health-empty-seats", "Empty officer seats", "executive officers"),
    ("health-reports", "Transition reports", "submitted, of those due in the year"),
    ("health-ballots", "Ballot turnout", "chapter votes on the year's closed ballots"),
]
# Hidden on the member home page and a CSS's landing page; shown on the region pages.
REGION_ONLY_IDS = ["tab-health", "careers-region-only", "trends-region-only"]
# Shown on the region pages and a CSS's landing page.
REGION_AND_CSS_IDS = ["tab-trends"]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


app.layout = html.Div(
    className="tt-region-dashboard",
    children=[
        dcc.Location(id="region-url", refresh=False),
        # Poll for the outer page's Bootstrap theme every 1.5s so callbacks
        # re-render figures with the correct plotly template on toggle.
        dcc.Interval(id="theme-poll", interval=1500, n_intervals=0),
        dcc.Store(id="theme-store", data="light"),
        dcc.Store(id="region-slug-store", data="national"),
        dcc.Store(id="ay-store", data=None),
        # Optional forced scope. When set (e.g. the member home page embeds this
        # app scoped to the viewer's own chapter via a hidden ``#cmt-dashboard-scope``
        # element read client-side), ``store_region`` locks the dashboard to it and
        # the region selector is hidden. ``None`` on the region/national pages.
        dcc.Store(id="scope-override-store", data=None),
        # Header row — region selector + academic-year selector.
        html.Div(
            className="d-flex flex-wrap align-items-end justify-content-between mb-3 gap-3",
            children=[
                html.Div(
                    id="region-scope-col",
                    style={"minWidth": "260px", "flex": "1 1 260px"},
                    children=[
                        html.Label(
                            "Region scope",
                            htmlFor="region-selector",
                            className="form-label small text-body-secondary mb-1",
                        ),
                        dcc.Dropdown(
                            id="region-selector",
                            options=[],
                            value="national",
                            clearable=False,
                            searchable=False,
                            className="tt-region-selector",
                        ),
                    ],
                ),
                # A Chapter Support Specialist's chapter filter, shown only on their landing
                # page; its options come from the server (``populate_support_chapters``).
                html.Div(
                    id="support-chapter-col",
                    style={"display": "none"},
                    children=[
                        html.Label(
                            "Chapter",
                            htmlFor="support-chapter-selector",
                            className="form-label small text-body-secondary mb-1",
                        ),
                        dcc.Dropdown(
                            id="support-chapter-selector",
                            options=[],
                            value=None,
                            clearable=False,
                            searchable=False,
                        ),
                    ],
                ),
                html.Div(
                    style={"minWidth": "200px", "flex": "0 1 200px"},
                    children=[
                        html.Label(
                            "Academic year",
                            htmlFor="ay-selector",
                            className="form-label small text-body-secondary mb-1",
                        ),
                        dcc.Dropdown(
                            id="ay-selector",
                            options=[],
                            clearable=False,
                            searchable=False,
                        ),
                    ],
                ),
            ],
        ),
        # KPI cards.
        html.Div(
            className="row g-2 mb-2",
            children=[_kpi_card(card_id, label, subtitle, note=True) for card_id, label, subtitle in KPI_CARDS],
        ),
        # Tabs.
        dcc.Tabs(
            id="dashboard-tabs",
            value="overview",
            className="tt-dashboard-tabs mb-3",
            children=[
                dcc.Tab(
                    label="Overview",
                    value="overview",
                    className="tt-dashboard-tab",
                    selected_className="tt-dashboard-tab--active",
                    children=html.Div(
                        className="row",
                        children=[
                            _panel("Student members by chapter", "members-by-chapter"),
                            _panel("Class year mix (student members, from expected graduation year)", "class-year-mix"),
                            _panel("Initiations by chapter", "initiations-by-chapter"),
                            _panel("Graduates by chapter", "graduates-by-chapter"),
                            _panel("Depledges by chapter", "depledges-by-chapter"),
                        ],
                    ),
                ),
                dcc.Tab(
                    label="Chapter Activity",
                    value="activity",
                    className="tt-dashboard-tab",
                    selected_className="tt-dashboard-tab--active",
                    children=html.Div(
                        className="row",
                        children=[
                            _panel("Events logged by chapter", "events-by-chapter"),
                            _panel("Submissions by chapter", "submissions-by-chapter"),
                            _panel("Tasks completed by chapter", "tasks-by-chapter"),
                            _panel("Trainings completed by chapter", "trainings-by-chapter"),
                            _panel("Average GPA", "gpa-by-chapter"),
                            _panel("Service hours", "service-hours-by-chapter"),
                        ],
                    ),
                ),
                dcc.Tab(
                    label="Chapter Scores",
                    value="scores",
                    className="tt-dashboard-tab",
                    selected_className="tt-dashboard-tab--active",
                    children=html.Div(
                        className="row",
                        children=[
                            # Total scores span the full row; the four section
                            # panels sit two-up on medium screens below.
                            _panel("Total scores by chapter", "scores-total-by-chapter"),
                            _panel(
                                "Brotherhood scores by chapter",
                                "scores-bro-by-chapter",
                                sm_cols=12,
                                md_cols=6,
                            ),
                            _panel(
                                "Operate scores by chapter",
                                "scores-ops-by-chapter",
                                sm_cols=12,
                                md_cols=6,
                            ),
                            _panel(
                                "Professional scores by chapter",
                                "scores-pro-by-chapter",
                                sm_cols=12,
                                md_cols=6,
                            ),
                            _panel(
                                "Service scores by chapter",
                                "scores-ser-by-chapter",
                                sm_cols=12,
                                md_cols=6,
                            ),
                        ],
                    ),
                ),
                dcc.Tab(
                    label="Recruitment & Careers",
                    value="recruitment",
                    className="tt-dashboard-tab",
                    selected_className="tt-dashboard-tab--active",
                    children=[
                        html.Div(
                            className="row",
                            children=[
                                _panel(
                                    "Top 10 recruiting chapters (initiations)",
                                    "top-recruiting-chapters",
                                    sm_cols=12,
                                    md_cols=6,
                                ),
                                _panel(
                                    "PNM retention rate by chapter",
                                    "retention-by-chapter",
                                    sm_cols=12,
                                    md_cols=6,
                                ),
                                _panel("Majors of study (current members)", "majors-breakdown"),
                                _panel("Where members work now (sized by members)", "current-employer-cloud"),
                                _panel(
                                    "Graduate employers (sized by hires)",
                                    "graduation-employer-cloud",
                                    sm_cols=12,
                                    md_cols=6,
                                ),
                                _panel(
                                    "Member organizations (sized by participants)",
                                    "member-organization-cloud",
                                    sm_cols=12,
                                    md_cols=6,
                                ),
                            ],
                        ),
                        html.Div(
                            id="careers-region-only",
                            className="row",
                            style={"display": "none"},
                            children=[
                                _panel(
                                    "Graduates who reported an employer, by chapter",
                                    "placement-by-chapter",
                                    sm_cols=12,
                                    md_cols=8,
                                ),
                                _panel("Graduates by degree", "graduates-by-degree", sm_cols=12, md_cols=4),
                            ],
                        ),
                    ],
                ),
                dcc.Tab(
                    id="tab-health",
                    label="Chapter Health",
                    value="health",
                    style={"display": "none"},
                    className="tt-dashboard-tab",
                    selected_className="tt-dashboard-tab--active",
                    children=[
                        html.Div(
                            className="row g-2 mb-2",
                            children=[_kpi_card(*card) for card in CHAPTER_COUNT_CARDS]
                            + [
                                _kpi_card(card_id, label, subtitle, note=card_id == "health-below-minimum")
                                for card_id, label, subtitle in HEALTH_CARDS
                            ],
                        ),
                        html.Div(
                            className="card shadow-sm bg-body-tertiary text-body border-0 mb-3",
                            children=[
                                html.Div("Chapters", className="card-header bg-transparent border-0 fw-semibold"),
                                html.Div(
                                    id="chapter-health-table",
                                    className="card-body table-responsive",
                                    style={"maxHeight": "40rem", "overflowY": "auto"},
                                ),
                            ],
                        ),
                        html.Div(
                            className="row",
                            children=[
                                _panel(
                                    "Active chapters by university recognition",
                                    "chapters-by-recognition",
                                    sm_cols=12,
                                    md_cols=6,
                                ),
                                _panel(
                                    "Active chapters by school calendar",
                                    "chapters-by-school-type",
                                    sm_cols=12,
                                    md_cols=6,
                                ),
                            ],
                        ),
                    ],
                ),
                dcc.Tab(
                    id="tab-trends",
                    label="Trends & Reach",
                    value="trends",
                    style={"display": "none"},
                    className="tt-dashboard-tab",
                    selected_className="tt-dashboard-tab--active",
                    children=[
                        html.Div(
                            className="row",
                            children=[
                                _panel(
                                    "Student members, initiations and graduates by academic year",
                                    "membership-trends",
                                ),
                                _panel(
                                    f"Officers and other student members signed in to CMT in the last {CMT_USE_DAYS} days",
                                    "cmt-use-by-chapter",
                                ),
                            ],
                        ),
                        html.Div(
                            id="trends-region-only",
                            className="row",
                            style={"display": "none"},
                            children=[
                                _panel(
                                    "Awards, job postings and volunteer nominations by academic year",
                                    "programs-by-year",
                                    sm_cols=12,
                                    md_cols=6,
                                ),
                                _panel("Alumni reach (living alumni)", "alumni-reach", sm_cols=12, md_cols=6),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# Region selection: URL → dropdown, dropdown → store
# ---------------------------------------------------------------------------


@app.callback(
    [Output("region-selector", "options"), Output("region-selector", "value")],
    Input("region-url", "pathname"),
)
def sync_region_from_url(pathname):
    options = region_options()
    slug = parse_region_slug(pathname)
    valid = {opt["value"] for opt in options}
    if slug not in valid:
        slug = "national"
    return options, slug


@app.callback(
    Output("region-slug-store", "data"),
    Input("region-selector", "value"),
    Input("scope-override-store", "data"),
    Input("support-chapter-selector", "value"),
)
def store_region(value, override, support_choice=None):
    # A forced scope (member home page, locked to the viewer's own chapter)
    # always wins over the region selector. On a Chapter Support Specialist's
    # landing page their chapter filter narrows it; get_scope_chapters still
    # holds them to their own chapters whatever is chosen.
    if override == SUPPORT_SCOPE:
        return support_choice or SUPPORT_SCOPE
    if override:
        return override
    return value or "national"


@app.callback(
    [
        Output("support-chapter-selector", "options"),
        Output("support-chapter-selector", "value"),
        Output("support-chapter-col", "style"),
    ],
    Input("scope-override-store", "data"),
)
def populate_support_chapters(override):
    if override != SUPPORT_SCOPE:
        return [], None, {"display": "none"}
    chapters = get_scope_chapters(SUPPORT_SCOPE).order_by("name")
    options = [{"label": "All my chapters", "value": SUPPORT_SCOPE}] + [
        {"label": chapter.name, "value": f"chapter_{chapter.slug}"} for chapter in chapters
    ]
    return options, SUPPORT_SCOPE, {"minWidth": "260px", "flex": "1 1 260px"}


# When embedded on the member home page, the template renders a hidden
# ``#cmt-dashboard-scope`` element carrying the viewer's own chapter scope
# (``chapter_<slug>``). Read it on load and push it into the override store so
# ``store_region`` locks every figure to that chapter. On the region/national
# pages the element is absent, so the store stays ``None`` (URL-driven scope).
app.clientside_callback(
    """
    function(_pathname) {
        try {
            var doc = (window.parent && window.parent.document)
                ? window.parent.document
                : document;
            var el = doc.getElementById('cmt-dashboard-scope');
            if (el) {
                var scope = el.getAttribute('data-scope');
                if (scope) {
                    return scope;
                }
            }
            return window.dash_clientside.no_update;
        } catch (e) {
            return window.dash_clientside.no_update;
        }
    }
    """,
    Output("scope-override-store", "data"),
    Input("region-url", "pathname"),
)


@app.callback(
    Output("region-scope-col", "style"),
    Input("scope-override-store", "data"),
)
def toggle_region_selector(override):
    # Hide the region selector entirely when the scope is forced (home page).
    if override:
        return {"display": "none"}
    return {"minWidth": "260px", "flex": "1 1 260px"}


@app.callback(
    [Output(element_id, "style") for element_id in REGION_ONLY_IDS + REGION_AND_CSS_IDS],
    Input("scope-override-store", "data"),
)
def toggle_region_only(override):
    # A forced scope means the member home page or a CSS's landing page; the
    # callbacks behind these panels also check who is looking.
    hidden = {"display": "none"}
    region_only = hidden if override else {}
    region_and_css = hidden if override and override != SUPPORT_SCOPE else {}
    return [region_only] * len(REGION_ONLY_IDS) + [region_and_css] * len(REGION_AND_CSS_IDS)


# ---------------------------------------------------------------------------
# Theme: poll outer document's data-bs-theme attribute via clientside JS.
# ---------------------------------------------------------------------------


# The interval fires client-side every 1.5s; the callback returns
# `dash_clientside.no_update` when the theme hasn't changed so the store isn't
# rewritten and downstream figure callbacks don't refire. Without this guard
# every server callback re-runs on every tick and the graphs never settle.
app.clientside_callback(
    """
    function(_n) {
        try {
            var root = (window.parent && window.parent.document)
                ? window.parent.document.documentElement
                : document.documentElement;
            var current = root.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
            // First tick: seed the tracker. Only push to the store when the
            // real DOM theme differs from the Store's default value ('light').
            if (window._ttRegionLastTheme === undefined) {
                window._ttRegionLastTheme = current;
                return current === 'light' ? window.dash_clientside.no_update : current;
            }
            if (window._ttRegionLastTheme === current) {
                return window.dash_clientside.no_update;
            }
            window._ttRegionLastTheme = current;
            return current;
        } catch (e) {
            return window.dash_clientside.no_update;
        }
    }
    """,
    Output("theme-store", "data"),
    Input("theme-poll", "n_intervals"),
)


# ---------------------------------------------------------------------------
# Academic year selection: populate the dropdown, mirror value into the store.
# ---------------------------------------------------------------------------


@app.callback(
    [Output("ay-selector", "options"), Output("ay-selector", "value")],
    Input("region-url", "pathname"),
)
def populate_ay_selector(_pathname):
    options = ay_options()
    return options, options[0]["value"] if options else None


@app.callback(Output("ay-store", "data"), Input("ay-selector", "value"))
def store_ay(value):
    return value


# ---------------------------------------------------------------------------
# KPI callbacks
# ---------------------------------------------------------------------------


def _kpi_int(value):
    if value is None:
        return "None"
    return f"{int(value):,}"


def _kpi_pct(rate):
    if rate is None:
        return "None"
    return f"{rate * 100:.0f}%"


def _count_note(current, prior, versus):
    """How a count moved since the year before, e.g. "▲ 12 (8%) vs AY 2024–25"."""
    change = current - prior
    if not change:
        return f"No change {versus}"
    text = f"{'▲' if change > 0 else '▼'} {abs(change):,}"
    if prior:
        text += f" ({abs(change) / prior * 100:.0f}%)"
    return f"{text} {versus}"


def _rate_note(current, prior, versus):
    """How a percentage moved since the year before, in percentage points."""
    if current is None or prior is None:
        return ""
    change = round((current - prior) * 100)
    if not change:
        return f"No change {versus}"
    return f"{'▲' if change > 0 else '▼'} {abs(change)} pts {versus}"


def _graduations(chapters, ay_start_year):
    """Graduation reports dated in the academic year, for members of `chapters`."""
    from thetatauCMT.forms.models import StatusChange

    ay_start, ay_end = ay_dates(ay_start_year)
    return StatusChange.objects.filter(
        reason="graduate",
        user__chapter__in=chapters,
        date_start__gte=ay_start.date(),
        date_start__lt=ay_end.date(),
    )


def _members_on(chapters, day):
    """Student members of `chapters` whose status covered `day`."""
    from thetatauCMT.users.models import UserStatusChange

    return (
        UserStatusChange.objects.filter(
            user__chapter__in=chapters, status__in=MEMBER_STATUSES, start__lte=day, end__gte=day
        )
        .values("user_id")
        .distinct()
        .count()
    )


def _census_on(chapters, day):
    """The living census as it stood on `day`. Deaths with no date on file stay out, as they do today."""
    from thetatauCMT.users.models import UserStatusChange

    return (
        UserStatusChange.objects.filter(
            user__chapter__in=chapters, status__in=CENSUS_STATUSES, start__lte=day, end__gte=day
        )
        .exclude(Q(user__deceased=True) & (Q(user__deceased_date__isnull=True) | Q(user__deceased_date__lte=day)))
        .values("user_id")
        .distinct()
        .count()
    )


# The academic-year counts, in the order of their cards.
AY_COUNT_KEYS = ("pnms", "initiations", "graduates", "prealums", "resignations")


def _ay_kpis(chapters, ay):
    """The academic-year numbers for `chapters`; retention and CommunityEdu are fractions or None."""
    from thetatauCMT.forms.models import Depledge, Initiation, PrematureAlumnus, ResignationProcess
    from thetatauCMT.trainings.services import chapter_completion_stats
    from thetatauCMT.users.models import UserStatusChange

    ay_start, ay_end = ay_dates(ay)
    ay_start_date, ay_end_date = ay_start.date(), ay_end.date()

    pnms = (
        UserStatusChange.objects.filter(
            status="pnm",
            start__gte=ay_start_date,
            start__lt=ay_end_date,
            user__chapter__in=chapters,
        )
        .values("user_id")
        .distinct()
        .count()
    )
    depledges = Depledge.objects.filter(
        user__chapter__in=chapters,
        date__gte=ay_start_date,
        date__lt=ay_end_date,
    ).count()
    completion_stats = chapter_completion_stats(start_date=ay_start_date, end_date=ay_end_date, chapters=chapters)
    completion_total = sum(stat.total for stat in completion_stats)
    completion_completed = sum(stat.completed for stat in completion_stats)

    return {
        "pnms": pnms,
        "initiations": Initiation.objects.filter(
            chapter__in=chapters,
            date__gte=ay_start_date,
            date__lt=ay_end_date,
        ).count(),
        # Distinct members: a future-dated graduate stays active and can be reported twice.
        "graduates": _graduations(chapters, ay).values("user_id").distinct().count(),
        "prealums": PrematureAlumnus.objects.filter(
            user__chapter__in=chapters,
            approved_exec=True,
            finished__gte=ay_start,
            finished__lt=ay_end,
        ).count(),
        "resignations": ResignationProcess.objects.filter(
            chapter__in=chapters,
            approved_exec=True,
            finished__gte=ay_start,
            finished__lt=ay_end,
        ).count(),
        "retention": max(0.0, 1.0 - depledges / pnms) if pnms else None,
        "community_edu": completion_completed / completion_total if completion_total else None,
    }


@app.callback(
    [Output(card_id, "children") for card_id, _, _ in KPI_CARDS]
    + [Output(f"{card_id}-note", "children") for card_id, _, _ in KPI_CARDS],
    [Input("region-slug-store", "data"), Input("ay-store", "data")],
)
def update_kpis(region_slug, ay_start_year):
    """The number cards, then their notes: how each moved since the year before, on the region pages."""
    from thetatauCMT.users.models import User

    chapters = get_scope_chapters(region_slug)
    census_chapters = get_scope_chapters(region_slug, include_inactive=True)
    ay = _ay_start(ay_start_year)

    total_members = User.objects.filter(chapter__in=chapters, current_status__in=MEMBER_STATUSES).count()
    living_census = (
        User.objects.filter(chapter__in=census_chapters, current_status__in=CENSUS_STATUSES)
        .exclude(deceased=True)
        .count()
    )
    current = _ay_kpis(chapters, ay)
    values = (
        _kpi_int(total_members),
        _kpi_int(living_census),
        *(_kpi_int(current[key]) for key in AY_COUNT_KEYS),
        _kpi_pct(current["retention"]),
        _kpi_pct(current["community_edu"]),
    )

    notes = ("",) * len(KPI_CARDS)
    if _region_or_css_view(region_slug):
        today = timezone.localdate()
        year_ago = _on_year(today, today.year - 1)
        prior = _ay_kpis(chapters, ay - 1)
        versus = f"vs {_ay_label(ay - 1)}"
        notes = (
            _count_note(total_members, _members_on(chapters, year_ago), "vs a year ago"),
            _count_note(living_census, _census_on(census_chapters, year_ago), "vs a year ago"),
            *(_count_note(current[key], prior[key], versus) for key in AY_COUNT_KEYS),
            _rate_note(current["retention"], prior["retention"], versus),
            _rate_note(current["community_edu"], prior["community_edu"], versus),
        )
    return values + notes


# ---------------------------------------------------------------------------
# Graph callbacks
# ---------------------------------------------------------------------------


def _bar_by_chapter(rows, y_label, theme):
    """Render a bar chart of `count` by chapter, coloured by region.

    Built with `go.Figure` + `go.Bar` rather than `px.bar` on purpose: in
    plotly 6.x, `px.bar` walks the shared default-template tree in
    `apply_default_cascade` and raises `ValueError: Invalid value` when the
    template's internal parent pointers get out of sync between concurrent
    requests (Django's threaded WSGI server hits this reliably). Constructing
    the figure directly bypasses that codepath entirely.
    """
    if not rows:
        return _empty_figure(theme, "No data for this period")
    df = pd.DataFrame(rows)
    # Normalize column names — some queries pull through `user__chapter__*`.
    rename = {
        "chapter__name": "Chapter",
        "chapter__region__name": "Region",
        "user__chapter__name": "Chapter",
        "user__chapter__region__name": "Region",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df["Region"] = df["Region"].fillna("Candidate")
    df = df.sort_values(["Region", "count"], ascending=[True, False])

    # Assign a stable colour per region from the palette (cycles if needed).
    regions_in_order = list(dict.fromkeys(df["Region"].tolist()))
    color_by_region = {region: REGION_PALETTE[i % len(REGION_PALETTE)] for i, region in enumerate(regions_in_order)}

    fig = go.Figure()
    for region in regions_in_order:
        group = df[df["Region"] == region]
        fig.add_trace(
            go.Bar(
                x=group["Chapter"].tolist(),
                y=group["count"].tolist(),
                name=region,
                marker_color=color_by_region[region],
                hovertemplate=(f"Region={region}<br>Chapter=%{{x}}<br>{y_label}=%{{y}}<extra></extra>"),
            )
        )
    fig.update_layout(
        barmode="group",
        bargap=0.15,
        xaxis_title=None,
        xaxis_tickangle=-45,
        yaxis_title=y_label,
        legend_title_text="Region",
    )
    return _apply_theme(fig, theme)


def _horizontal_bar_top_n(rows, label_key, value_key, x_label, theme, top_n=10, region_key=None):
    """Render a top-N horizontal bar chart, largest bar at the top.

    When `region_key` is provided, bars are coloured by region using the same
    palette as `_bar_by_chapter` so recruitment charts stay visually
    consistent with the region-scoped charts above them.
    """
    if not rows:
        return _empty_figure(theme, "No data for this period")
    df = pd.DataFrame(rows)
    if label_key not in df.columns or value_key not in df.columns:
        return _empty_figure(theme, "No data for this period")
    df = df.dropna(subset=[label_key])
    df = df[df[value_key].fillna(0) > 0]
    if df.empty:
        return _empty_figure(theme, "No data for this period")
    df = df.sort_values(value_key, ascending=False).head(top_n)
    # plotly draws the first item at the bottom of a horizontal bar chart;
    # reverse the rows so the largest value ends up on top.
    df = df.iloc[::-1]

    if region_key and region_key in df.columns:
        regions_series = df[region_key].fillna("Candidate")
        regions_in_order = list(dict.fromkeys(regions_series.tolist()))
        color_by_region = {region: REGION_PALETTE[i % len(REGION_PALETTE)] for i, region in enumerate(regions_in_order)}
        marker_colors = [color_by_region[r] for r in regions_series.tolist()]
    else:
        marker_colors = REGION_PALETTE[0]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df[value_key].tolist(),
            y=df[label_key].tolist(),
            orientation="h",
            marker_color=marker_colors,
            text=df[value_key].tolist(),
            textposition="outside",
            cliponaxis=False,
            hovertemplate=f"%{{y}}<br>{x_label}=%{{x}}<extra></extra>",
        )
    )
    fig.update_layout(
        showlegend=False,
        bargap=0.15,
        xaxis_title=x_label,
        yaxis_title=None,
    )
    return _apply_theme(fig, theme)


def _treemap_from_rows(rows, label_key, value_key, theme, value_label="Graduates", top_n=None):
    """Render a treemap where each rectangle's area is proportional to its
    value. Used in place of a word cloud (plotly ships no wordcloud trace)
    so the tag-cloud "biggest is most common" affordance survives.
    """
    if not rows:
        return _empty_figure(theme, "No data for this period")
    df = pd.DataFrame(rows)
    if label_key not in df.columns or value_key not in df.columns:
        return _empty_figure(theme, "No data for this period")
    df = df.dropna(subset=[label_key])
    df = df[df[value_key].fillna(0) > 0]
    if df.empty:
        return _empty_figure(theme, "No data for this period")
    df = df.sort_values(value_key, ascending=False)
    if top_n:
        df = df.head(top_n)

    fig = go.Figure(
        go.Treemap(
            labels=df[label_key].tolist(),
            parents=[""] * len(df),
            values=df[value_key].tolist(),
            textinfo="label+value",
            hovertemplate=f"%{{label}}<br>{value_label}=%{{value}}<extra></extra>",
            marker=dict(colors=[REGION_PALETTE[i % len(REGION_PALETTE)] for i in range(len(df))]),
        )
    )
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
    return _apply_theme(fig, theme)


def _add_reference_line(fig, value, label):
    """A dashed line across the chart at `value`: the figure its bars roll up to."""
    fig.add_hline(
        y=value,
        line_dash="dash",
        line_color="#888888",
        annotation_text=label.format(value),
        annotation_position="top left",
    )
    return fig


def _bar_by_term(rows, y_label, theme, value_format):
    """One chapter's academic year: a bar per term, with how many members reported it."""
    if not rows:
        return _empty_figure(theme, "No data for this period")
    values = [row["value"] for row in rows]
    fig = go.Figure(
        go.Bar(
            x=[f"{YearTermModel.TERMS.get_value(row['term'])} {row['year']}" for row in rows],
            y=values,
            text=[value_format.format(value) for value in values],
            textposition="outside",
            cliponaxis=False,
            customdata=[row["members"] for row in rows],
            marker_color=REGION_PALETTE[0],
            hovertemplate=f"%{{x}}<br>{y_label}=%{{text}}<br>Members reporting=%{{customdata}}<extra></extra>",
        )
    )
    fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title=y_label)
    return _apply_theme(fig, theme)


@app.callback(
    Output("members-by-chapter", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def members_by_chapter(region_slug, theme):
    from thetatauCMT.users.models import User

    chapters = get_scope_chapters(region_slug)
    rows = list(
        User.objects.filter(chapter__in=chapters, current_status__in=MEMBER_STATUSES)
        .values("chapter__name", "chapter__region__name")
        .annotate(count=Count("id"))
    )
    return _bar_by_chapter(rows, "Members", theme)


@app.callback(
    Output("class-year-mix", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def class_year_mix(region_slug, theme):
    """Student members by class: counts for one chapter, each chapter's mix for more.

    Class comes from the expected graduation year, which members keep current, not
    the class year recorded when they pledged.
    """
    from thetatauCMT.users.models import User

    today = timezone.localdate()
    counts = defaultdict(lambda: dict.fromkeys(CLASS_STANDINGS, 0))
    for row in (
        User.objects.filter(chapter__in=get_scope_chapters(region_slug), current_status__in=MEMBER_STATUSES)
        .values("chapter__name", "graduation_year")
        .annotate(count=Count("id"))
    ):
        counts[row["chapter__name"]][class_standing(row["graduation_year"], today)] += row["count"]
    if not counts:
        return _empty_figure(theme, "No student members")

    if _is_chapter_scope(region_slug):
        (mix,) = counts.values()
        values = [mix[standing] for standing in CLASS_STANDINGS]
        fig = go.Figure(
            go.Bar(
                x=CLASS_STANDINGS,
                y=values,
                text=values,
                textposition="outside",
                cliponaxis=False,
                marker_color=CLASS_STANDING_COLORS[: len(CLASS_STANDINGS)],
                hovertemplate="%{x}<br>Members=%{y}<extra></extra>",
            )
        )
        fig.update_layout(showlegend=False, xaxis_title=None, yaxis_title="Members")
        return _apply_theme(fig, theme)

    totals = {name: sum(mix.values()) for name, mix in counts.items()}
    leaving = {
        name: sum(mix[standing] for standing in CLASS_STANDINGS[-2:]) / totals[name] for name, mix in counts.items()
    }
    # Chapters about to lose the largest share of their members come first.
    order = sorted(counts, key=lambda name: (-leaving[name], name))
    fig = go.Figure()
    for standing, color in zip(CLASS_STANDINGS, CLASS_STANDING_COLORS):
        fig.add_trace(
            go.Bar(
                x=order,
                y=[round(counts[name][standing] / totals[name] * 100, 1) for name in order],
                customdata=[counts[name][standing] for name in order],
                name=standing,
                marker_color=color,
                hovertemplate=f"Chapter=%{{x}}<br>{standing}=%{{customdata}} (%{{y:.0f}}%)<extra></extra>",
            )
        )
    fig.update_layout(
        barmode="stack",
        bargap=0.15,
        xaxis_title=None,
        xaxis_tickangle=-45,
        yaxis_title="Share of student members (%)",
        legend_title_text="Class",
    )
    return _apply_theme(fig, theme)


@app.callback(
    Output("initiations-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def initiations_by_chapter(region_slug, ay_start_year, theme):
    from thetatauCMT.forms.models import Initiation

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    rows = list(
        Initiation.objects.filter(
            chapter__in=chapters,
            date__gte=ay_start.date(),
            date__lt=ay_end.date(),
        )
        .values("chapter__name", "chapter__region__name")
        .annotate(count=Count("id"))
    )
    return _bar_by_chapter(rows, "Initiations", theme)


@app.callback(
    Output("graduates-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def graduates_by_chapter(region_slug, ay_start_year, theme):
    rows = list(
        _graduations(get_scope_chapters(region_slug), ay_start_year)
        .values("user__chapter__name", "user__chapter__region__name")
        .annotate(count=Count("user", distinct=True))
    )
    return _bar_by_chapter(rows, "Graduates", theme)


@app.callback(
    Output("depledges-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def depledges_by_chapter(region_slug, ay_start_year, theme):
    from thetatauCMT.forms.models import Depledge

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    rows = list(
        Depledge.objects.filter(
            user__chapter__in=chapters,
            date__gte=ay_start.date(),
            date__lt=ay_end.date(),
        )
        .values("user__chapter__name", "user__chapter__region__name")
        .annotate(count=Count("id"))
    )
    return _bar_by_chapter(rows, "Depledges", theme)


@app.callback(
    Output("events-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def events_by_chapter(region_slug, ay_start_year, theme):
    from thetatauCMT.events.models import Event

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    rows = list(
        Event.objects.filter(
            chapter__in=chapters,
            date__gte=ay_start.date(),
            date__lt=ay_end.date(),
        )
        .values("chapter__name", "chapter__region__name")
        .annotate(count=Count("id"))
    )
    return _bar_by_chapter(rows, "Events", theme)


@app.callback(
    Output("submissions-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def submissions_by_chapter(region_slug, ay_start_year, theme):
    from thetatauCMT.submissions.models import Submission

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    rows = list(
        Submission.objects.filter(
            chapter__in=chapters,
            date__gte=ay_start.date(),
            date__lt=ay_end.date(),
        )
        .values("chapter__name", "chapter__region__name")
        .annotate(count=Count("id"))
    )
    return _bar_by_chapter(rows, "Submissions", theme)


@app.callback(
    Output("tasks-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def tasks_by_chapter(region_slug, ay_start_year, theme):
    from thetatauCMT.tasks.models import TaskChapter

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    rows = list(
        TaskChapter.objects.filter(
            chapter__in=chapters,
            date__gte=ay_start.date(),
            date__lt=ay_end.date(),
        )
        .values("chapter__name", "chapter__region__name")
        .annotate(count=Count("id"))
    )
    return _bar_by_chapter(rows, "Tasks completed", theme)


@app.callback(
    Output("trainings-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def trainings_by_chapter(region_slug, ay_start_year, theme):
    from thetatauCMT.trainings.models import Training

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    rows = list(
        Training.objects.filter(
            user__chapter__in=chapters,
            completed=True,
            completed_time__gte=ay_start,
            completed_time__lt=ay_end,
        )
        .values("user__chapter__name", "user__chapter__region__name")
        .annotate(count=Count("id"))
    )
    return _bar_by_chapter(rows, "Trainings completed", theme)


@app.callback(
    Output("gpa-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def gpa_by_chapter(region_slug, ay_start_year, theme):
    """Average GPA: by term for one chapter; by chapter, against the overall average, for more."""
    from thetatauCMT.users.models import UserSemesterGPA

    gpas = UserSemesterGPA.objects.filter(user__chapter__in=get_scope_chapters(region_slug)).filter(
        _ay_terms(ay_start_year)
    )
    if _is_chapter_scope(region_slug):
        rows = list(
            gpas.values("year", "term")
            .annotate(value=Avg("gpa"), members=Count("user", distinct=True))
            .order_by("year")
        )
        return _bar_by_term(rows, "Average GPA", theme, "{:.2f}")
    rows = list(gpas.values("user__chapter__name", "user__chapter__region__name").annotate(count=Avg("gpa")))
    for row in rows:
        row["count"] = round(row["count"], 2)
    fig = _bar_by_chapter(rows, "Average GPA", theme)
    if rows:
        _add_reference_line(fig, gpas.aggregate(average=Avg("gpa"))["average"], "Average {:.2f}")
    return fig


@app.callback(
    Output("service-hours-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def service_hours_by_chapter(region_slug, ay_start_year, theme):
    """Service hours: by term for one chapter; by chapter, against the average chapter, for more."""
    from thetatauCMT.users.models import UserSemesterServiceHours

    hours = UserSemesterServiceHours.objects.filter(user__chapter__in=get_scope_chapters(region_slug)).filter(
        _ay_terms(ay_start_year)
    )
    if _is_chapter_scope(region_slug):
        rows = list(
            hours.values("year", "term")
            .annotate(value=Sum("service_hours"), members=Count("user", distinct=True))
            .order_by("year")
        )
        return _bar_by_term(rows, "Service hours", theme, "{:,.0f}")
    rows = list(hours.values("user__chapter__name", "user__chapter__region__name").annotate(count=Sum("service_hours")))
    for row in rows:
        row["count"] = round(row["count"])
    fig = _bar_by_chapter(rows, "Service hours", theme)
    if rows:
        _add_reference_line(fig, sum(row["count"] for row in rows) / len(rows), "Average chapter {:,.0f}")
    return fig


# ---------------------------------------------------------------------------
# Chapter Scores tab
# ---------------------------------------------------------------------------


def _score_rows(region_slug, ay_start_year, section=None):
    """Aggregate `ScoreChapter.score` for the selected AY, optionally scoped
    to a single section (`Bro`/`Ops`/`Pro`/`Ser`).

    ScoreChapter is a `YearTermModel` — an academic year spans two rows per
    chapter+type: Fall (year=ay, term='fa') plus Spring (year=ay+1, term='sp').
    """
    from thetatauCMT.scores.models import ScoreChapter

    chapters = get_scope_chapters(region_slug)
    qs = ScoreChapter.objects.filter(chapter__in=chapters).filter(_ay_terms(ay_start_year))
    if section is not None:
        qs = qs.filter(type__section=section)
    return list(qs.values("chapter__name", "chapter__region__name").annotate(count=Sum("score")).order_by())


@app.callback(
    Output("scores-total-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def scores_total_by_chapter(region_slug, ay_start_year, theme):
    rows = _score_rows(region_slug, ay_start_year)
    return _bar_by_chapter(rows, "Total score", theme)


@app.callback(
    Output("scores-bro-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def scores_bro_by_chapter(region_slug, ay_start_year, theme):
    rows = _score_rows(region_slug, ay_start_year, section="Bro")
    return _bar_by_chapter(rows, "Brotherhood score", theme)


@app.callback(
    Output("scores-ops-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def scores_ops_by_chapter(region_slug, ay_start_year, theme):
    rows = _score_rows(region_slug, ay_start_year, section="Ops")
    return _bar_by_chapter(rows, "Operate score", theme)


@app.callback(
    Output("scores-pro-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def scores_pro_by_chapter(region_slug, ay_start_year, theme):
    rows = _score_rows(region_slug, ay_start_year, section="Pro")
    return _bar_by_chapter(rows, "Professional score", theme)


@app.callback(
    Output("scores-ser-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def scores_ser_by_chapter(region_slug, ay_start_year, theme):
    rows = _score_rows(region_slug, ay_start_year, section="Ser")
    return _bar_by_chapter(rows, "Service score", theme)


# ---------------------------------------------------------------------------
# Recruitment & Careers tab
# ---------------------------------------------------------------------------


@app.callback(
    Output("majors-breakdown", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def majors_breakdown(region_slug, theme):
    """Top majors across current active members in scope."""
    from thetatauCMT.users.models import User

    chapters = get_scope_chapters(region_slug)
    rows = list(
        User.objects.filter(
            chapter__in=chapters,
            current_status__in=MEMBER_STATUSES,
            major__isnull=False,
        )
        .values("major__major")
        .annotate(count=Count("id"))
    )
    # Normalize the FK-traversal key into the label column the helper expects.
    for row in rows:
        row["Major"] = row.pop("major__major")
    return _horizontal_bar_top_n(rows, label_key="Major", value_key="count", x_label="Members", theme=theme, top_n=15)


@app.callback(
    Output("top-recruiting-chapters", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def top_recruiting_chapters(region_slug, ay_start_year, theme):
    """10 chapters with the most initiations in the selected AY."""
    from thetatauCMT.forms.models import Initiation

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    rows = list(
        Initiation.objects.filter(
            chapter__in=chapters,
            date__gte=ay_start.date(),
            date__lt=ay_end.date(),
        )
        .values("chapter__name", "chapter__region__name")
        .annotate(count=Count("id"))
    )
    for row in rows:
        row["Chapter"] = row.pop("chapter__name")
        row["Region"] = row.pop("chapter__region__name")
    return _horizontal_bar_top_n(
        rows,
        label_key="Chapter",
        value_key="count",
        x_label="Initiations",
        theme=theme,
        top_n=10,
        region_key="Region",
    )


@app.callback(
    Output("retention-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def retention_by_chapter(region_slug, ay_start_year, theme):
    """Per-chapter PNM retention: `1 - depledges / pnms` in the AY.

    Only chapters that recorded at least one PNM in the window are shown; a
    zero-PNM chapter would divide-by-zero, so it's silently dropped rather
    than counted as 100% retention.
    """
    from thetatauCMT.forms.models import Depledge
    from thetatauCMT.users.models import UserStatusChange

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    ay_start_date, ay_end_date = ay_start.date(), ay_end.date()

    pnm_rows = (
        UserStatusChange.objects.filter(
            status="pnm",
            start__gte=ay_start_date,
            start__lt=ay_end_date,
            user__chapter__in=chapters,
        )
        .values("user__chapter__name", "user__chapter__region__name")
        .annotate(count=Count("user_id", distinct=True))
    )
    depledge_rows = (
        Depledge.objects.filter(
            user__chapter__in=chapters,
            date__gte=ay_start_date,
            date__lt=ay_end_date,
        )
        .values("user__chapter__name")
        .annotate(count=Count("id"))
    )
    depledge_by_chapter = {r["user__chapter__name"]: r["count"] for r in depledge_rows}

    rows = []
    for row in pnm_rows:
        chapter_name = row["user__chapter__name"]
        pnms = row["count"] or 0
        if not pnms:
            continue
        depledges = depledge_by_chapter.get(chapter_name, 0)
        rate = max(0.0, 1.0 - (depledges / pnms)) * 100
        rows.append(
            {
                "Chapter": chapter_name,
                "Region": row["user__chapter__region__name"] or "Candidate",
                "count": round(rate, 1),
            }
        )
    if not rows:
        return _empty_figure(theme, "No PNM data for this period")

    df = pd.DataFrame(rows).sort_values(["Region", "count"], ascending=[True, False])
    regions_in_order = list(dict.fromkeys(df["Region"].tolist()))
    color_by_region = {region: REGION_PALETTE[i % len(REGION_PALETTE)] for i, region in enumerate(regions_in_order)}

    fig = go.Figure()
    for region in regions_in_order:
        group = df[df["Region"] == region]
        fig.add_trace(
            go.Bar(
                x=group["Chapter"].tolist(),
                y=group["count"].tolist(),
                name=region,
                marker_color=color_by_region[region],
                text=[f"{v:.0f}%" for v in group["count"].tolist()],
                textposition="outside",
                hovertemplate=(f"Region={region}<br>Chapter=%{{x}}<br>Retention=%{{y:.1f}}%<extra></extra>"),
            )
        )
    fig.update_layout(
        barmode="group",
        bargap=0.15,
        xaxis_title=None,
        xaxis_tickangle=-45,
        yaxis_title="Retention (%)",
        yaxis_range=[0, 105],
        legend_title_text="Region",
    )
    return _apply_theme(fig, theme)


@app.callback(
    Output("current-employer-cloud", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def current_employer_cloud(region_slug, theme):
    """Treemap of the employers members have on their profile right now.

    A snapshot rather than an academic-year window: it answers "where do our
    members work" from `User.employer`, whereas `graduation_employer_cloud`
    answers "who hired this year's graduates" from their status change.
    """
    from thetatauCMT.users.models import User

    chapters = get_scope_chapters(region_slug)
    rows = list(
        User.objects.filter(
            chapter__in=chapters,
            current_status__in=CAREER_STATUSES,
            employer__isnull=False,
        )
        .values("employer__name")
        .annotate(count=Count("id"))
    )
    for row in rows:
        row["Employer"] = row.pop("employer__name")
    return _treemap_from_rows(
        rows,
        label_key="Employer",
        value_key="count",
        theme=theme,
        value_label="Members",
        top_n=40,
    )


@app.callback(
    Output("graduation-employer-cloud", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def graduation_employer_cloud(region_slug, ay_start_year, theme):
    """Treemap of employers named on graduate StatusChange rows in the AY.

    Rectangle area is proportional to the number of graduates who reported
    that employer — the closest plotly-native equivalent of a word cloud.
    """
    rows = list(
        _graduations(get_scope_chapters(region_slug), ay_start_year)
        .filter(employer__isnull=False)
        .values("employer__name")
        .annotate(count=Count("id"))
    )
    for row in rows:
        row["Employer"] = row.pop("employer__name")
    return _treemap_from_rows(rows, label_key="Employer", value_key="count", theme=theme)


@app.callback(
    Output("placement-by-chapter", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def placement_by_chapter(region_slug, ay_start_year, theme):
    """Share of the year's graduates who reported an employer, by chapter, against the overall share."""
    if not _region_view(region_slug):
        return _empty_figure(theme)
    rows = list(
        _graduations(get_scope_chapters(region_slug), ay_start_year)
        .values("user__chapter__name", "user__chapter__region__name")
        .annotate(
            graduates=Count("user", distinct=True),
            placed=Count("user", distinct=True, filter=Q(employer__isnull=False)),
        )
    )
    for row in rows:
        row["count"] = round(row["placed"] / row["graduates"] * 100)
    fig = _bar_by_chapter(rows, "Reported an employer (%)", theme)
    graduates = sum(row["graduates"] for row in rows)
    if graduates:
        _add_reference_line(fig, sum(row["placed"] for row in rows) / graduates * 100, "Overall {:.0f}%")
    return fig


@app.callback(
    Output("graduates-by-degree", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def graduates_by_degree(region_slug, ay_start_year, theme):
    """The year's graduates by the degree they finished."""
    from thetatauCMT.forms.models import StatusChange

    if not _region_view(region_slug):
        return _empty_figure(theme)
    degrees = dict(degree.value for degree in StatusChange.DEGREES)
    rows = [
        {"Degree": degrees.get(row["degree"], row["degree"]), "count": row["count"]}
        for row in _graduations(get_scope_chapters(region_slug), ay_start_year)
        .values("degree")
        .annotate(count=Count("user", distinct=True))
    ]
    return _horizontal_bar_top_n(rows, label_key="Degree", value_key="count", x_label="Graduates", theme=theme)


@app.callback(
    Output("member-organization-cloud", "figure"),
    [
        Input("region-slug-store", "data"),
        Input("ay-store", "data"),
        Input("theme-store", "data"),
    ],
)
def member_organization_cloud(region_slug, ay_start_year, theme):
    """Treemap of external organizations members participated in during the AY.

    Rectangle area is proportional to the number of members who reported
    participation in that organization — mirroring the graduate-employer
    treemap.
    """
    from thetatauCMT.users.models import UserOrgParticipate

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    rows = list(
        UserOrgParticipate.objects.filter(
            user__chapter__in=chapters,
            organization__isnull=False,
            start__lt=ay_end.date(),
            end__gte=ay_start.date(),
        )
        .values("organization__name")
        .annotate(count=Count("user", distinct=True))
    )
    for row in rows:
        row["Organization"] = row.pop("organization__name")
    return _treemap_from_rows(rows, label_key="Organization", value_key="count", theme=theme, value_label="Members")


# ---------------------------------------------------------------------------
# Chapter Health tab (region pages, National Officers)
# ---------------------------------------------------------------------------


def chapter_health_rows(chapters, ay):
    """One row per chapter, by region: student members, overdue tasks, balance, empty
    officer seats, and the year's transition reports and ballot votes."""
    from thetatauCMT.support.overview import chapter_overview

    chapters = list(
        chapters.annotate(
            student_members=Count("members", filter=Q(members__current_status__in=MEMBER_STATUSES), distinct=True)
        )
    )
    overview = {row["chapter"].pk: row for row in chapter_overview(chapters, year=ay)}
    return [
        {
            "chapter": chapter,
            "members": chapter.student_members,
            "balance": chapter.balance,
            **{
                key: overview[chapter.pk][key]
                for key in (
                    "overdue",
                    "missing",
                    "reports_submitted",
                    "reports_due",
                    "ballots_voted",
                    "ballots_eligible",
                )
            },
        }
        for chapter in sorted(chapters, key=lambda chapter: (chapter.region.name, chapter.name))
    ]


def _of(part, whole):
    """ "3 of 4 (75%)", or "None" when there was nothing to count."""
    if not whole:
        return "None"
    return f"{part:,} of {whole:,} ({part / whole * 100:.0f}%)"


def _share(part, whole):
    if not whole:
        return "None"
    return f"{part / whole * 100:.0f}%"


def _money(amount):
    return f"-${abs(amount):,.2f}" if amount < 0 else f"${amount:,.2f}"


def _health_table(rows, minimum):
    """One row per chapter; chapters below the minimum size carry a badge."""
    if not rows:
        return html.P("No chapters in this scope.", className="text-body-secondary mb-0")
    headers = [
        "Chapter",
        "Region",
        "Student members",
        "Overdue tasks",
        "Balance owed",
        "Empty officer seats",
        "Transition reports",
        "Ballot votes",
    ]
    body = []
    for row in rows:
        chapter = row["chapter"]
        members = [f"{row['members']:,}"]
        if row["members"] < minimum:
            members.append(html.Span(f"Below {minimum}", className="badge text-bg-warning ms-2"))
        body.append(
            html.Tr(
                [
                    html.Th(
                        html.A(chapter.name, href=reverse("chapters:detail", kwargs={"slug": chapter.slug})),
                        scope="row",
                    ),
                    html.Td(chapter.region.name),
                    html.Td(members),
                    html.Td(f"{row['overdue']:,}"),
                    html.Td(_money(row["balance"])),
                    html.Td(f"{len(row['missing'])}: {', '.join(row['missing'])}" if row["missing"] else "0"),
                    html.Td(_of(row["reports_submitted"], row["reports_due"])),
                    html.Td(_of(row["ballots_voted"], row["ballots_eligible"])),
                ]
            )
        )
    return html.Table(
        className="table table-sm table-hover align-middle mb-0",
        children=[
            html.Caption("Chapter health for the selected scope and academic year", className="visually-hidden"),
            html.Thead(html.Tr([html.Th(header, scope="col") for header in headers])),
            html.Tbody(body),
        ],
    )


@app.callback(
    [Output(card_id, "children") for card_id, _, _ in HEALTH_CARDS]
    + [Output("health-below-minimum-note", "children"), Output("chapter-health-table", "children")],
    [Input("region-slug-store", "data"), Input("ay-store", "data")],
)
def chapter_health(region_slug, ay_start_year):
    """The Chapter Health cards, then the minimum-size note and the table."""
    if not _region_view(region_slug):
        return [""] * (len(HEALTH_CARDS) + 1) + [None]
    minimum = min_chapter_size()
    rows = chapter_health_rows(get_scope_chapters(region_slug), _ay_start(ay_start_year))
    owed = sum(row["balance"] for row in rows if row["balance"] > 0)
    return [
        _kpi_int(sum(row["members"] < minimum for row in rows)),
        _kpi_int(sum(bool(row["overdue"]) for row in rows)),
        f"${owed:,.0f}",
        _kpi_int(sum(len(row["missing"]) for row in rows)),
        _share(sum(row["reports_submitted"] for row in rows), sum(row["reports_due"] for row in rows)),
        _share(sum(row["ballots_voted"] for row in rows), sum(row["ballots_eligible"] for row in rows)),
        f"fewer than {minimum} student members",
        _health_table(rows, minimum),
    ]


@app.callback(
    [Output(card_id, "children") for card_id, _, _ in CHAPTER_COUNT_CARDS]
    + [Output("chapters-by-recognition", "figure"), Output("chapters-by-school-type", "figure")],
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def chapter_counts(region_slug, theme):
    """Chapters, candidate chapters and closed chapters, and how the active ones are recognized and scheduled."""
    if not _region_view(region_slug):
        return [""] * len(CHAPTER_COUNT_CARDS) + [_empty_figure(theme), _empty_figure(theme)]
    every = get_scope_chapters(region_slug, include_inactive=True)
    active = every.filter(active=True)
    recognition = dict(choice.value for choice in Chapter.RECOGNITION)
    calendars = dict(Chapter.TYPES)
    by_recognition = [
        {"Recognition": recognition.get(row["recognition"], row["recognition"]), "count": row["count"]}
        for row in active.values("recognition").annotate(count=Count("id"))
    ]
    by_calendar = [
        {"Calendar": calendars.get(row["school_type"], row["school_type"]), "count": row["count"]}
        for row in active.values("school_type").annotate(count=Count("id"))
    ]
    return [
        _kpi_int(active.filter(candidate_chapter=False).count()),
        _kpi_int(active.filter(candidate_chapter=True).count()),
        _kpi_int(every.filter(active=False).count()),
        _horizontal_bar_top_n(by_recognition, "Recognition", "count", "Chapters", theme),
        _horizontal_bar_top_n(by_calendar, "Calendar", "count", "Chapters", theme),
    ]


# ---------------------------------------------------------------------------
# Trends & Reach tab (region pages, National Officers)
# ---------------------------------------------------------------------------


def _year_labels(years):
    """Academic-year axis labels; the last year is still under way."""
    return [_ay_label(ay) + (" (to date)" if ay == years[-1] else "") for ay in years]


@app.callback(
    Output("membership-trends", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def membership_trends(region_slug, theme):
    """Each recent academic year's initiations and graduates, and its student members on today's date."""
    from thetatauCMT.forms.models import Initiation

    if not _region_or_css_view(region_slug):
        return _empty_figure(theme)
    # Closed chapters still count toward the years they were open.
    chapters = get_scope_chapters(region_slug, include_inactive=True)
    today = timezone.localdate()
    years = _recent_years()
    members, initiations, graduates = [], [], []
    for ay in years:
        ay_start, ay_end = ay_dates(ay)
        members.append(_members_on(chapters, _on_year(today, ay if today.month >= 7 else ay + 1)))
        initiations.append(
            Initiation.objects.filter(chapter__in=chapters, date__gte=ay_start.date(), date__lt=ay_end.date()).count()
        )
        graduates.append(_graduations(chapters, ay).values("user_id").distinct().count())
    labels = _year_labels(years)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=labels, y=initiations, name="Initiations", marker_color=REGION_PALETTE[0]))
    fig.add_trace(go.Bar(x=labels, y=graduates, name="Graduates", marker_color=REGION_PALETTE[1]))
    fig.add_trace(
        go.Scatter(
            x=labels,
            y=members,
            name=f"Student members on {today:%b} {today.day}",
            mode="lines+markers",
            yaxis="y2",
            marker_color=REGION_PALETTE[2],
        )
    )
    fig.update_layout(
        barmode="group",
        xaxis_title=None,
        yaxis_title="Initiations and graduates",
        yaxis2=dict(title="Student members", overlaying="y", side="right", rangemode="tozero"),
    )
    _apply_theme(fig, theme)
    # Room for the right-hand axis title.
    fig.update_layout(margin=dict(r=60))
    return fig


@app.callback(
    Output("programs-by-year", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def programs_by_year(region_slug, theme):
    """Awards granted, job postings and volunteer nominations in each recent academic year."""
    from thetatauCMT.awards.models import AwardGrant
    from thetatauCMT.jobs.models import Job
    from thetatauCMT.nominations.models import Nomination

    if not _region_view(region_slug):
        return _empty_figure(theme)
    chapters = get_scope_chapters(region_slug, include_inactive=True)
    awards = AwardGrant.objects.active().filter(
        Q(recipient_member__chapter__in=chapters)
        | Q(recipient_chapter__in=chapters)
        | Q(recipient_region__chapters__in=chapters)
    )
    jobs = Job.objects.filter(deleted=False, created_by__chapter__in=chapters)
    nominations = Nomination.objects.filter(
        Q(nominee__chapter__in=chapters) | Q(nominee__isnull=True, nominator__chapter__in=chapters)
    )
    years = _recent_years()
    series = {"Awards granted": [], "Job postings": [], "Volunteer nominations": []}
    for ay in years:
        start, end = ay_dates(ay)
        series["Awards granted"].append(
            awards.filter(effective_date__gte=start.date(), effective_date__lt=end.date())
            .values("pk")
            .distinct()
            .count()
        )
        series["Job postings"].append(jobs.filter(created__gte=start, created__lt=end).count())
        series["Volunteer nominations"].append(nominations.filter(created__gte=start, created__lt=end).count())
    labels = _year_labels(years)
    fig = go.Figure()
    for (name, counts), color in zip(series.items(), REGION_PALETTE):
        fig.add_trace(go.Bar(x=labels, y=counts, name=name, marker_color=color))
    fig.update_layout(barmode="group", xaxis_title=None, yaxis_title="Count")
    return _apply_theme(fig, theme)


@app.callback(
    Output("alumni-reach", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def alumni_reach(region_slug, theme):
    """How many living alumni can actually be reached, by email and by mail."""
    from thetatauCMT.email_tracking.models import TrackedEmail
    from thetatauCMT.users.models import User

    if not _region_view(region_slug):
        return _empty_figure(theme)
    alumni = User.objects.filter(
        chapter__in=get_scope_chapters(region_slug, include_inactive=True), current_status__in=ALUMNI_STATUSES
    ).exclude(deceased=True)
    living = alumni.count()
    if not living:
        return _empty_figure(theme, "No living alumni")
    open_to_contact = alumni.filter(no_contact=False)
    # An address counts as bouncing when the latest message sent to the member bounced.
    last_bounce = TrackedEmail.objects.filter(user=OuterRef("pk")).order_by("-sent_at").values("bounced_at")[:1]
    by_email = (
        open_to_contact.filter(unsubscribe_email=False)
        .exclude(email="")
        .annotate(last_bounce=Subquery(last_bounce))
        .filter(last_bounce__isnull=True)
    )
    stages = [
        ("Living alumni", living),
        ("Open to contact", open_to_contact.count()),
        ("Reachable by email", by_email.count()),
        ("Reachable by mail", open_to_contact.filter(address__isnull=False).count()),
    ]
    # Plotly draws the first bar at the bottom; reverse so the stages read top down.
    stages.reverse()
    fig = go.Figure(
        go.Bar(
            x=[count for _, count in stages],
            y=[label for label, _ in stages],
            orientation="h",
            text=[f"{count:,} ({count / living * 100:.0f}%)" for _, count in stages],
            textposition="outside",
            cliponaxis=False,
            marker_color=REGION_PALETTE[0],
            hovertemplate="%{y}=%{x:,}<extra></extra>",
        )
    )
    # Headroom for the count labels drawn past the end of each bar.
    fig.update_layout(showlegend=False, xaxis_title="Alumni", yaxis_title=None, xaxis_range=[0, living * 1.35])
    return _apply_theme(fig, theme)


@app.callback(
    Output("cmt-use-by-chapter", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def cmt_use_by_chapter(region_slug, theme):
    """Share of each chapter's officers, and of its other student members, who signed in recently.

    Officers are the executive officers, who get officer access to CMT; committee chairs
    count with the other members. Each group's overall share is in the legend.
    """
    from thetatauCMT.users.models import User

    if not _region_or_css_view(region_slug):
        return _empty_figure(theme)
    officer = Q(current_roles__overlap=sorted(CHAPTER_OFFICER))
    recent = Q(last_login__gte=timezone.now() - datetime.timedelta(days=CMT_USE_DAYS))
    rows = sorted(
        User.objects.filter(chapter__in=get_scope_chapters(region_slug), current_status__in=MEMBER_STATUSES)
        .values("chapter__name")
        .annotate(
            members=Count("id"),
            signed_in=Count("id", filter=recent),
            officers=Count("id", filter=officer),
            officers_signed_in=Count("id", filter=officer & recent),
        ),
        key=lambda row: row["chapter__name"],
    )
    if not rows:
        return _empty_figure(theme, "No student members")
    for row in rows:
        row["others"] = row["members"] - row["officers"]
        row["others_signed_in"] = row["signed_in"] - row["officers_signed_in"]

    fig = go.Figure()
    for label, group, color in (
        ("Officers", "officers", REGION_PALETTE[0]),
        ("Other members", "others", REGION_PALETTE[1]),
    ):
        total = sum(row[group] for row in rows)
        signed_in = sum(row[f"{group}_signed_in"] for row in rows)
        fig.add_trace(
            go.Bar(
                x=[row["chapter__name"] for row in rows],
                # A chapter with nobody in the group gets no bar rather than 0%.
                y=[round(row[f"{group}_signed_in"] / row[group] * 100) if row[group] else None for row in rows],
                customdata=[[row[f"{group}_signed_in"], row[group]] for row in rows],
                name=f"{label} ({signed_in / total * 100:.0f}% overall)" if total else label,
                marker_color=color,
                hovertemplate=(
                    f"%{{x}}<br>{label}: %{{customdata[0]}} of %{{customdata[1]}} signed in (%{{y}}%)<extra></extra>"
                ),
            )
        )
    fig.update_layout(
        barmode="group",
        bargap=0.15,
        xaxis_title=None,
        xaxis_tickangle=-45,
        yaxis_title="Signed in (%)",
        yaxis_range=[0, 105],
    )
    _apply_theme(fig, theme)
    # Above the bars: the rotated chapter names below would hide the overall shares.
    fig.update_layout(legend=dict(yanchor="bottom", y=1.02, xanchor="right", x=1))
    return fig
