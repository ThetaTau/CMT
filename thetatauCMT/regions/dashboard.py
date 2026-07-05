"""Regional / National dashboard rendered via django-plotly-dash.

The same `RegionDashboard` app powers both `/regions/national/` (all chapters)
and `/regions/<slug>/` (chapters in one region). The active region is inferred
from the browser URL via `dcc.Location`; national officers can override the
scope with the region dropdown at the top of the layout.
"""

import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dcc, html
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django_plotly_dash import DjangoDash

from core.models import academic_encompass_start_end_date
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.regions.models import Region

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

# Distinct qualitative palette; falls back to Plotly D3 for extra regions.
REGION_PALETTE = px.colors.qualitative.Bold + px.colors.qualitative.D3


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


def get_scope_chapters(region_slug):
    """Return the queryset of active chapters in scope for `region_slug`.

    * `national` — all active chapters
    * `candidate_chapter` — all active candidate chapters
    * any other slug — chapters whose region slug matches
    """
    qs = Chapter.objects.exclude(active=False).select_related("region")
    if region_slug == "national" or not region_slug:
        return qs
    if region_slug == "candidate_chapter":
        return qs.filter(candidate_chapter=True)
    return qs.filter(region__slug=region_slug)


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


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _kpi_card(card_id, label, subtitle=""):
    return html.Div(
        className="col-6 col-md-4 col-xl-2 mb-3",
        children=html.Div(
            className="card h-100 shadow-sm bg-body-tertiary text-body border-0",
            children=html.Div(
                className="card-body text-center",
                children=[
                    html.H6(label, className="card-subtitle text-body-secondary text-uppercase small mb-2"),
                    html.H3(id=card_id, className="card-title fw-bold mb-1", children="—"),
                    html.Div(subtitle, className="text-body-secondary small") if subtitle else None,
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
        # Header row — region selector + academic-year selector.
        html.Div(
            className="d-flex flex-wrap align-items-end justify-content-between mb-3 gap-3",
            children=[
                html.Div(
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
            children=[
                _kpi_card("kpi-total-members", "Student members today", "current active + activepend"),
                _kpi_card("kpi-pnms", "PNMs", "prospective status started"),
                _kpi_card("kpi-initiations", "Initiations", "date within academic year"),
                _kpi_card("kpi-prealums", "Prealumni", "approved by exec"),
                _kpi_card("kpi-resignations", "Resignations", "approved by exec"),
                _kpi_card("kpi-retention", "PNM retention", "1 − depledges / PNMs"),
            ],
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
                            _panel("Initiations by chapter", "initiations-by-chapter"),
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


@app.callback(Output("region-slug-store", "data"), Input("region-selector", "value"))
def store_region(value):
    return value or "national"


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
        return "—"
    return f"{int(value):,}"


@app.callback(
    [
        Output("kpi-total-members", "children"),
        Output("kpi-pnms", "children"),
        Output("kpi-initiations", "children"),
        Output("kpi-prealums", "children"),
        Output("kpi-resignations", "children"),
        Output("kpi-retention", "children"),
    ],
    [Input("region-slug-store", "data"), Input("ay-store", "data")],
)
def update_kpis(region_slug, ay_start_year):
    from thetatauCMT.forms.models import Depledge, Initiation, PrematureAlumnus, ResignationProcess
    from thetatauCMT.users.models import User, UserStatusChange

    chapters = get_scope_chapters(region_slug)
    ay_start, ay_end = ay_dates(ay_start_year)
    ay_start_date, ay_end_date = ay_start.date(), ay_end.date()

    total_members = User.objects.filter(chapter__in=chapters, current_status__in=ACTIVE_STATUSES).count()

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

    initiations = Initiation.objects.filter(
        chapter__in=chapters,
        date__gte=ay_start_date,
        date__lt=ay_end_date,
    ).count()

    depledges = Depledge.objects.filter(
        user__chapter__in=chapters,
        date__gte=ay_start_date,
        date__lt=ay_end_date,
    ).count()

    prealums = PrematureAlumnus.objects.filter(
        user__chapter__in=chapters,
        approved_exec=True,
        finished__gte=ay_start,
        finished__lt=ay_end,
    ).count()

    resignations = ResignationProcess.objects.filter(
        chapter__in=chapters,
        approved_exec=True,
        finished__gte=ay_start,
        finished__lt=ay_end,
    ).count()

    retention = "—"
    if pnms:
        rate = max(0.0, 1.0 - (depledges / pnms)) * 100
        retention = f"{rate:.0f}%"

    return (
        _kpi_int(total_members),
        _kpi_int(pnms),
        _kpi_int(initiations),
        _kpi_int(prealums),
        _kpi_int(resignations),
        retention,
    )


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


@app.callback(
    Output("members-by-chapter", "figure"),
    [Input("region-slug-store", "data"), Input("theme-store", "data")],
)
def members_by_chapter(region_slug, theme):
    from thetatauCMT.users.models import User

    chapters = get_scope_chapters(region_slug)
    rows = list(
        User.objects.filter(chapter__in=chapters, current_status__in=ACTIVE_STATUSES)
        .values("chapter__name", "chapter__region__name")
        .annotate(count=Count("id"))
    )
    return _bar_by_chapter(rows, "Members", theme)


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


# ---------------------------------------------------------------------------
# Chapter Scores tab
# ---------------------------------------------------------------------------


def _score_rows(region_slug, ay_start_year, section=None):
    """Aggregate `ScoreChapter.score` for the selected AY, optionally scoped
    to a single section (`Bro`/`Ops`/`Pro`/`Ser`).

    ScoreChapter is a `YearTermModel` — an academic year spans two rows per
    chapter+type: Fall (year=ay, term='fa') plus Spring (year=ay+1, term='sp').
    """
    from django.db.models import Q, Sum

    from thetatauCMT.scores.models import ScoreChapter

    chapters = get_scope_chapters(region_slug)
    ay = int(ay_start_year) if ay_start_year is not None else academic_encompass_start_end_date()[0].year
    ay_filter = Q(year=ay, term="fa") | Q(year=ay + 1, term="sp")

    qs = ScoreChapter.objects.filter(chapter__in=chapters).filter(ay_filter)
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
