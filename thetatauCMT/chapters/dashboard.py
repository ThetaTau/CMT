import datetime
import textwrap

import dash
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from django.conf import settings
from django.db.models import Avg, Count

from core.models import semester_encompass_start_end_date
from thetatauCMT.users.models import User, UserSemesterGPA, UserStatusChange

if __name__ == "__main__":
    import os
    import sys
    from pathlib import Path

    import django

    app = dash.Dash(__name__)
    app.expanded_callback = app.callback
    os.chdir("../")
    print(os.getcwd())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    print("Django %s" % django.get_version())
    if Path(sys.path[0]) == Path(__file__).parent:
        # Something is adding the __file__ to sys path and causing issues
        # as forms are being imported things wrong in pycharm
        sys.path.pop(0)
    django.setup()
else:
    from django_plotly_dash import DjangoDash

    # See `regions/dashboard.py` for the rationale — django-plotly-dash 2.5.1
    # doesn't route dash 3+/4's new `_dash-component-suites` URL scheme, so
    # locally-served plotly.min.js 404s and dcc.Graphs never mount. Load it
    # from the CDN at the exact version bundled with `plotly==6.8.0` (v3.6.0).
    app = DjangoDash(
        "Dashboard",
        serve_locally=False,
        external_scripts=["https://cdn.plot.ly/plotly-3.6.0.min.js"],
    )


# -------------------------------------------------------------------------------
# STYLING ASSETS
# -------------------------------------------------------------------------------

COLORS = {
    "Actives": "#ff9f43",
    "Aways": "#a29bfe",
    "PNMs": "#57606f",
    "Depledges": "#d63031",
    "Alumni": "#2e86de",
    "Fall": "#AC2414",
    "Winter": "#FCC30C",
    "Spring": "#E8472D",
    "Summer": "#000000",
}

now = datetime.datetime.now()
YEARS = [x for x in range(2018, now.year + 1)]

# Class applied to every dashboard panel so Bootstrap 5.3 theme tokens
# (`bg-body-tertiary`, `text-body`) drive colors in both light and dark modes
# without having to keep hex values in Python.
_PANEL_CLASS = "tt-dashboard-panel card border-0 shadow-sm bg-body-tertiary text-body"

_PANEL_BASE = dict(
    borderRadius=8,
    margin=10,
    padding=15,
    position="relative",
)
style = {
    "slider": {**_PANEL_BASE, "margin": 5, "padding": 30},
    "number": {**_PANEL_BASE, "width": "20%", "textAlign": "center"},
    "big_graph": {**_PANEL_BASE, "flex": "1 1 auto", "minWidth": 0},
    # Year selector is a compact control — shrink it to leave room for the
    # majors-of-study pie chart next to it.
    "small_graph": {**_PANEL_BASE, "flex": "0 0 220px", "maxWidth": "260px"},
}


def _theme_template(theme):
    return "plotly_dark" if theme == "dark" else "plotly_white"


def _apply_theme(fig, theme):
    """Set a theme-aware template and transparent backgrounds on `fig`."""
    fig.update_layout(
        template=_theme_template(theme),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def layout(fig, title, YEARS, theme="light"):
    """Apply the shared axis + title layout used by legacy chapter graphs.

    `theme` is optional so tests that call ``layout(fig, title, YEARS)``
    positionally keep working; callbacks pass the current theme so the
    figure background matches the outer light / dark mode.
    """
    fig.update_layout(
        template=_theme_template(theme),
        title={
            "text": title,
            "x": 0.5,
            "y": 0.9,
            "font": dict(family="Arial", size=22),
            "xanchor": "center",
            "yanchor": "top",
        },
        xaxis=dict(
            showline=True,
            showgrid=False,
            showticklabels=True,
            linewidth=2,
            ticks="outside",
            tickfont=dict(family="Arial", size=12),
            ticktext=YEARS,
            tickvals=YEARS,
        ),
        yaxis=dict(showgrid=False, zeroline=False, showline=False, showticklabels=False),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )


def fetch_stats(initial, final):
    change = 0
    try:
        change = round(((final - initial) / initial * 100), 2)
    except ZeroDivisionError:
        pass
    except TypeError:
        pass
    if change > 0:
        return html.H2(f"+{change}%", style=dict(color="#20bf6b", textAlign="center"))
    if change < 0:
        return html.H2(f"{change}%", style=dict(color="#ff6b6b", textAlign="center"))
    else:
        return html.H2("N/A", style=dict(color="#b2bec3", textAlign="center"))


# -------------------------------------------------------------------------------

app.layout = html.Div(
    children=[
        # invisible button for initial loading
        html.Button(id="invisible-button", style={"display": "none"}),
        dcc.Store(id="chapter-data", storage_type="local"),
        # Theme sync — a clientside interval mirrors the outer page's
        # `data-bs-theme` attribute into `theme-store` so figure callbacks
        # can re-render with `plotly_dark` / `plotly_white` templates.
        dcc.Interval(id="theme-poll", interval=1500, n_intervals=0),
        dcc.Store(id="theme-store", data="light"),
        html.Div(
            children=[html.H1("Status Dashboard", className="mb-0")],
            style=dict(display="flex", flexDirection="row", marginBottom=10, marginTop=20),
        ),
        html.Div(
            className=_PANEL_CLASS,
            children=[
                html.P("Select date range:", className="mb-2"),
                dcc.RangeSlider(
                    id="years-slider",
                    dots=True,
                    step=0.5,
                ),
            ],
            style=style["slider"],
        ),
        html.Div(
            className=_PANEL_CLASS,
            children=[
                html.P("Select status: ", className="mb-2"),
                dcc.Dropdown(
                    id="status-dropdown",
                    options=[
                        {"label": "Actives", "value": "Actives"},
                        {"label": "Aways", "value": "Aways"},
                        {"label": "PNMs", "value": "PNMs"},
                        {"label": "Depledges", "value": "Depledges"},
                        {"label": "Alumni", "value": "Alumni"},
                    ],
                    value=["Actives", "Aways"],
                    multi=True,
                ),
            ],
            style=style["big_graph"],
        ),
        html.Div(
            className=_PANEL_CLASS,
            children=[
                # NOTE: dash 4.x's `dcc.Loading` drops nested Dash components
                # from its `children` prop during render, leaving an empty
                # wrapper. Graphs go straight into the panel instead — Dash 4
                # already shows loading state on the target output.
                dcc.Graph(id="composition-graph", config={"displaylogo": False}),
            ],
            style=style["big_graph"],
        ),
        html.Div(
            children=[
                html.Div(
                    className=_PANEL_CLASS,
                    children=[
                        html.Div(id="actives-num"),
                        html.H6(
                            "Actives",
                            style=dict(color=COLORS["Actives"], textAlign="center"),
                        ),
                        html.H6(
                            "[ activepend + active + alumnipend]",
                            className="text-body-secondary",
                            style=dict(fontSize=14, textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    className=_PANEL_CLASS,
                    children=[
                        html.Div(id="aways-num"),
                        html.H6(
                            "Aways",
                            style=dict(color=COLORS["Aways"], textAlign="center"),
                        ),
                        html.H6(
                            "[ coop + military + study abroad ]",
                            className="text-body-secondary",
                            style=dict(fontSize=14, textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    className=_PANEL_CLASS,
                    children=[
                        html.Div(id="pnms-num"),
                        html.H6(
                            "PNMs",
                            style=dict(color=COLORS["PNMs"], textAlign="center"),
                        ),
                        html.H6(
                            "[ pnm ]",
                            className="text-body-secondary",
                            style=dict(fontSize=14, textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    className=_PANEL_CLASS,
                    children=[
                        html.Div(id="depledges-num"),
                        html.H6(
                            "Depledges",
                            style=dict(color=COLORS["Depledges"], textAlign="center"),
                        ),
                        html.H6(
                            "[ depledge ]",
                            className="text-body-secondary",
                            style=dict(fontSize=14, textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    className=_PANEL_CLASS,
                    children=[
                        html.Div(id="alumni-num"),
                        html.H6(
                            "Alumni",
                            style=dict(color=COLORS["Alumni"], textAlign="center"),
                        ),
                        html.H6(
                            "[ alumni ]",
                            className="text-body-secondary",
                            style=dict(fontSize=14, textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
            ],
            style=dict(display="flex", flexDirection="row"),
        ),
        html.Div(children=[html.P(id="years-text", style=dict(textAlign="center"))]),
        html.Div(
            children=[
                html.Div(
                    className=_PANEL_CLASS,
                    children=[
                        html.P("Select year: ", className="mb-2"),
                        dcc.Dropdown(id="years-dropdown", value=now.year),
                    ],
                    style=style["small_graph"],
                ),
                html.Div(
                    className=_PANEL_CLASS,
                    children=[
                        # Graph 3: Majors of Study — see note on Loading above.
                        dcc.Graph(id="majors-graph", config={"displaylogo": False}),
                    ],
                    style=style["big_graph"],
                ),
            ],
            style=dict(display="flex", flexDirection="row"),
        ),
        html.Div(
            className=_PANEL_CLASS,
            children=[
                # Graph 4: Average GPA over time — see note on Loading above.
                dcc.Graph(id="gpa-graph", config={"displaylogo": False}),
            ],
            style=style["big_graph"],
        ),
    ]
)


# Clientside — mirror the outer page's `data-bs-theme` attribute into the store
# so figure callbacks re-render with the appropriate Plotly template.
# Returns `dash_clientside.no_update` when the theme hasn't changed; without
# this guard every 1.5s interval tick would re-write the store and cascade
# through every figure callback, causing a permanent POST loop.
app.clientside_callback(
    """
    function(_n) {
        try {
            var root = (window.parent && window.parent.document)
                ? window.parent.document.documentElement
                : document.documentElement;
            var current = root.getAttribute('data-bs-theme') === 'dark' ? 'dark' : 'light';
            if (window._ttChapterLastTheme === undefined) {
                window._ttChapterLastTheme = current;
                return current === 'light' ? window.dash_clientside.no_update : current;
            }
            if (window._ttChapterLastTheme === current) {
                return window.dash_clientside.no_update;
            }
            window._ttChapterLastTheme = current;
            return current;
        } catch (e) {
            return window.dash_clientside.no_update;
        }
    }
    """,
    Output("theme-store", "data"),
    Input("theme-poll", "n_intervals"),
)


# invisible button
@app.expanded_callback(
    [
        Output("chapter-data", "data"),
        Output("years-slider", "marks"),
        Output("years-slider", "min"),
        Output("years-slider", "max"),
        Output("years-slider", "value"),
        Output("years-dropdown", "options"),
        Output("years-dropdown", "value"),
    ],
    [Input("invisible-button", "n_clicks")],
)
def load_chapter_data(clicks, **kwargs):
    user = kwargs.get("user", None)
    if user is None and settings.DEBUG:
        user = User.objects.get(username="venturafranklin@gmail.com")
    elif user.is_anonymous:
        raise PreventUpdate
    chapter = user.current_chapter
    dfs = []
    year_terms_marks = {}
    for year in YEARS:
        for term, date_info in {"Spring": "-03-01", "Fall": "-10-01"}.items():
            date_filter = datetime.datetime.strptime(f"{year}{date_info}", "%Y-%m-%d")
            start, end = semester_encompass_start_end_date(date_filter)
            # In filters should be start of status < end of semester
            #                      end of status > start of semester
            status = dict(
                UserStatusChange.objects.values_list("status")
                .filter(
                    user__chapter=chapter,
                    start__lte=end,
                    end__gte=start,
                )
                .annotate(count=Count("status"))
            )
            majors = dict(
                User.objects.values_list("major__major")
                .filter(
                    chapter=chapter,
                    status__start__lte=end,
                    status__end__gte=start,
                    status__status__in=[
                        "active",
                        "activepend",
                        "alumnipend",
                        "activeCC",
                    ],
                )
                .order_by()
                .annotate(count=Count("major"))
            )
            gpas = UserSemesterGPA.objects.filter(
                user__chapter=chapter,
                term=UserSemesterGPA.get_term(date_filter),
                year=date_filter.year,
            ).aggregate(Avg("gpa"), Count("gpa"))
            status.update(gpas)
            status.update({"majors": [majors]})
            status.update({"year": year, "term": term})
            df_year_term = pd.DataFrame(status, index=[f"{term} {year}"])
            dfs.append(df_year_term)
            year_terms_marks[year + {"Spring": 0, "Fall": 0.5}[term]] = {
                "label": f"{term} {year}",
                # Colour is applied via `.dash-slider-mark` / `.rc-slider-mark-text`
                # in `project.css`, which follows the Bootstrap theme in light + dark.
            }
    align_status = {
        "Actives": ["active", "activepend", "alumnipend"],
        "Aways": ["away"],
        "PNMs": ["pnm"],
        "Depledges": ["depledge"],
        "Alumni": ["alumni"],
    }
    df = pd.concat(dfs, sort=True)
    for main_status, align_statuss in align_status.items():
        # Only sum columns that actually appear in the dataframe. The old
        # `all(status in df.columns)` guard forced the entire count to 0 when
        # ANY sub-status was absent — so e.g. a chapter with only "active"
        # users (no `activepend` / `alumnipend`) would always show Actives = 0.
        present = [status for status in align_statuss if status in df.columns]
        if present:
            df[main_status] = df[present].sum(axis=1)
        else:
            df[main_status] = 0
    df["Year Term"] = df.index
    year_terms = [{"label": val, "value": val} for val in df["Year Term"]]
    # Present the year dropdown newest-first so the current term is at the top.
    year_terms_newest_first = list(reversed(year_terms))
    # Default the range slider to the last two years (four semester marks); the
    # user can still drag back further to inspect deeper history.
    mark_keys = list(year_terms_marks.keys())
    default_start_idx = max(0, len(mark_keys) - 4)
    return (
        df.to_dict(orient="records"),
        year_terms_marks,
        mark_keys[0],
        mark_keys[-1],
        [mark_keys[default_start_idx], mark_keys[-1]],
        year_terms_newest_first,
        year_terms_newest_first[0]["value"],
    )


def _count_card(end_val, start_val):
    """KPI-card body: the count at the end of the selected range, with a
    small coloured delta showing change since the start of the range."""
    try:
        end_int = int(end_val)
    except (TypeError, ValueError):
        end_int = 0
    change = None
    try:
        change = round(((end_val - start_val) / start_val * 100), 2)
    except (ZeroDivisionError, TypeError):
        pass
    if change is None or change == 0:
        delta_color = "#b2bec3"
        delta_text = "no change" if change == 0 else "None"
    elif change > 0:
        delta_color = "#20bf6b"
        delta_text = f"▲ +{change}%"
    else:
        delta_color = "#ff6b6b"
        delta_text = f"▼ {change}%"
    return html.Div(
        [
            html.H2(f"{end_int:,}", style={"textAlign": "center", "margin": 0}),
            html.Div(
                delta_text,
                style={"color": delta_color, "textAlign": "center", "fontSize": 12},
            ),
        ]
    )


@app.callback(
    [
        Output("years-text", "children"),
        Output("actives-num", "children"),
        Output("aways-num", "children"),
        Output("pnms-num", "children"),
        Output("depledges-num", "children"),
        Output("alumni-num", "children"),
    ],
    [Input("chapter-data", "data"), Input("years-slider", "value")],
)
def update_text(data, years, **kwargs):
    statuss = ["Actives", "Aways", "PNMs", "Depledges", "Alumni"]
    df = pd.DataFrame.from_dict(data)
    df = df.fillna(0)
    if years is None or "year" not in df:
        raise PreventUpdate
    start, end = years
    start_term = "Fall" if str(start).endswith(".5") else "Spring"
    end_term = "Fall" if str(end).endswith(".5") else "Spring"
    outs = []
    for status in statuss:
        start_val = df[(df["year"] == int(start)) & (df["term"] == start_term)][status].iloc[0]
        end_val = df[(df["year"] == int(end)) & (df["term"] == end_term)][status].iloc[0]
        outs.append(_count_card(end_val, start_val))
    return (
        f"Showing counts at {end_term} {int(end)}. " f"Change vs. {start_term} {int(start)} shown below each number.",
        *outs,
    )


@app.callback(
    Output("composition-graph", "figure"),
    [
        Input("chapter-data", "data"),
        Input("years-slider", "value"),
        Input("status-dropdown", "value"),
        Input("theme-store", "data"),
    ],
    [
        State("years-slider", "marks"),
    ],
)
def members_graph(data, years, status, theme="light", year_info=None, **kwargs):
    df = pd.DataFrame.from_dict(data)
    df = df.fillna(0)
    if year_info is None or "Year Term" not in df:
        raise PreventUpdate
    start_indx = df.index[df["Year Term"] == year_info[str(years[0])]["label"]]
    end_indx = df.index[df["Year Term"] == year_info[str(years[-1])]["label"]]
    try:
        fig = px.line(
            df.iloc[start_indx[0] : end_indx[0] + 1],
            x="Year Term",
            y=status,
            title="Membership Composition",
            color_discrete_map=COLORS,
            # Markers keep the graph readable when the range collapses to a
            # single point (a line with one point renders as empty).
            markers=True,
        )
        fig.update_traces(marker=dict(size=8), line=dict(width=2))
        fig.update_layout(showlegend=False, yaxis_title="", xaxis_title="")
    except KeyError:
        raise PreventUpdate
    else:
        return _apply_theme(fig, theme)


@app.callback(
    Output("majors-graph", "figure"),
    [
        Input("chapter-data", "data"),
        Input("years-dropdown", "value"),
        Input("theme-store", "data"),
    ],
)
def majors_graph(data, yearterm, theme="light", **kwargs):
    df = pd.DataFrame.from_dict(data)
    df = df.fillna(0)
    try:
        majors = df[df["Year Term"] == yearterm]["majors"].iloc[0]
    except (IndexError, KeyError):
        raise PreventUpdate
    labels = list(majors.keys())
    labels = ["<br>".join(textwrap.wrap(label, width=26)) for label in labels]
    values = list(majors.values())
    fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.35)])
    fig.update_layout(
        title={
            "text": f"Major of Study {yearterm}",
            "x": 0.5,
            "y": 0.9,
            "font": dict(family="Arial", size=22),
            "xanchor": "center",
            "yanchor": "top",
        },
    )
    return _apply_theme(fig, theme)


@app.callback(
    Output("gpa-graph", "figure"),
    [
        Input("chapter-data", "data"),
        Input("years-slider", "value"),
        Input("theme-store", "data"),
    ],
    [State("years-slider", "marks")],
)
def gpa_graph(data, years, theme="light", year_info=None, **kwargs):
    df = pd.DataFrame.from_dict(data)
    df = df.fillna(0)
    if year_info is None or "Year Term" not in df:
        raise PreventUpdate
    start_indx = df.index[df["Year Term"] == year_info[str(years[0])]["label"]]
    end_indx = df.index[df["Year Term"] == year_info[str(years[-1])]["label"]]
    fig = px.line(
        df.iloc[start_indx[0] : end_indx[0] + 1],
        x="Year Term",
        y="gpa__avg",
        title="Average GPA",
        hover_data=["gpa__count"],
        markers=True,
    )
    fig.update_traces(marker=dict(size=8), line=dict(width=2))
    fig.update_layout(showlegend=False, yaxis_title="", xaxis_title="")
    return _apply_theme(fig, theme)


if __name__ == "__main__":
    app.run_server(debug=False)
