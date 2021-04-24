import dash
import datetime
import textwrap
import pandas as pd
from django.db.models import Count, Avg
import plotly.graph_objects as go
import plotly.express as px
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from dash.exceptions import PreventUpdate
from django.conf import settings
from core.models import semester_encompass_start_end_date
from users.models import (
    User,
    UserStatusChange,
    UserSemesterGPA,
)

if __name__ == "__main__":
    import os
    import sys
    import django
    from pathlib import Path

    app = dash.Dash(__name__)
    app.expanded_callback = app.callback
    os.chdir("../")
    print(os.getcwd())
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local_ventura")
    print("Django %s" % django.get_version())
    if Path(sys.path[0]) == Path(__file__).parent:
        # Something is adding the __file__ to sys path and causing issues
        # as forms are being imported things wrong in pycharm
        sys.path.pop(0)
    django.setup()
else:
    from django_plotly_dash import DjangoDash

    app = DjangoDash("Dashboard")


# -------------------------------------------------------------------------------
# STYLING ASSETS
# -------------------------------------------------------------------------------

COLORS = {
    "Actives": "#ff9f43",
    "Inactives": "#a29bfe",
    "Pledges": "#57606f",
    "Depledges": "#d63031",
    "Alumni": "#2e86de",
    "Fall": "#AC2414",
    "Winter": "#FCC30C",
    "Spring": "#E8472D",
    "Summer": "#000000",
}

now = datetime.datetime.now()
YEARS = [x for x in range(2018, now.year + 1)]

style = {
    "slider": dict(
        borderRadius=5,
        backgroundColor="#f9f9f9",
        margin=5,
        padding=30,
        position="relative",
        boxShadow="2px 2px 2px lightgrey",
    ),
    "number": dict(
        borderRadius=5,
        backgroundColor="#f9f9f9",
        margin=10,
        padding=15,
        width="20%",
        position="relative",
        boxShadow="2px 2px 2px lightgrey",
    ),
    "big_graph": dict(
        borderRadius=5,
        backgroundColor="#f9f9f9",
        margin=10,
        padding=15,
        position="relative",
        boxShadow="2px 2px 2px lightgrey",
    ),
    "small_graph": dict(
        borderRadius=5,
        backgroundColor="#f9f9f9",
        margin=10,
        padding=15,
        width="48%",
        position="relative",
        boxShadow="2px 2px 2px lightgrey",
    ),
}


def layout(fig, title, YEARS):
    fig.update_layout(
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
            linecolor="rgb(204, 204, 204)",
            linewidth=2,
            ticks="outside",
            tickfont=dict(family="Arial", size=12, color="rgb(82,82,82)"),
            ticktext=YEARS,
            tickvals=YEARS,
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, showline=False, showticklabels=False
        ),
        plot_bgcolor="#F9F9F9",
        paper_bgcolor="#F9F9F9",
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
        html.Div(
            children=[html.H1("Status Dashboard")],
            style=dict(
                display="flex", flexDirection="row", marginBottom=10, marginTop=20
            ),
        ),
        html.Div(
            children=[
                html.P("Select date range:"),
                dcc.RangeSlider(id="years-slider", dots=True, step=0.5,),
            ],
            style=style["slider"],
        ),
        html.Div(
            children=[
                html.P("Select status: "),
                dcc.Dropdown(
                    id="status-dropdown",
                    options=[
                        {"label": "Actives", "value": "Actives"},
                        {"label": "Inactives", "value": "Inactives"},
                        {"label": "Pledges", "value": "Pledges"},
                        {"label": "Depledges", "value": "Depledges"},
                        {"label": "Alumni", "value": "Alumni"},
                    ],
                    value=["Actives", "Inactives"],
                    multi=True,
                ),
            ],
            style=style["big_graph"],
        ),
        html.Div(
            children=[
                dcc.Loading(
                    type="default",
                    children=[
                        # Graph 1: Chapter size over time
                        dcc.Graph(id="composition-graph"),
                    ],
                )
            ],
            style=style["big_graph"],
        ),
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.Div(id="actives-num"),
                        html.H6(
                            "Actives",
                            style=dict(color=COLORS["Actives"], textAlign="center"),
                        ),
                        html.H6(
                            "[ activepend + active + alumnipend]",
                            style=dict(fontSize=14, color="grey", textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    children=[
                        html.Div(id="inactives-num"),
                        html.H6(
                            "Inactives",
                            style=dict(color=COLORS["Inactives"], textAlign="center"),
                        ),
                        html.H6(
                            "[ away ]",
                            style=dict(fontSize=14, color="grey", textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    children=[
                        html.Div(id="pledges-num"),
                        html.H6(
                            "Pledges",
                            style=dict(color=COLORS["Pledges"], textAlign="center"),
                        ),
                        html.H6(
                            "[ pledge ]",
                            style=dict(fontSize=14, color="grey", textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    children=[
                        html.Div(id="depledges-num"),
                        html.H6(
                            "Depledges",
                            style=dict(color=COLORS["Depledges"], textAlign="center"),
                        ),
                        html.H6(
                            "[ depledge ]",
                            style=dict(fontSize=14, color="grey", textAlign="center"),
                        ),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    children=[
                        html.Div(id="alumni-num"),
                        html.H6(
                            "Alumni",
                            style=dict(color=COLORS["Alumni"], textAlign="center"),
                        ),
                        html.H6(
                            "[ alumni ]",
                            style=dict(fontSize=14, color="grey", textAlign="center"),
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
                    children=[
                        html.P("Select year: "),
                        dcc.Dropdown(id="years-dropdown", value=now.year),
                    ],
                    style=style["small_graph"],
                ),
                html.Div(
                    children=[
                        dcc.Loading(
                            type="default",
                            children=[
                                # Graph 3: Majors of Study
                                dcc.Graph(id="majors-graph"),
                            ],
                        )
                    ],
                    style=style["big_graph"],
                ),
            ],
            style=dict(display="flex", flexDirection="row"),
        ),
        html.Div(
            children=[
                dcc.Loading(
                    type="default",
                    children=[
                        # Graph 4: Average GPA over time
                        dcc.Graph(id="gpa-graph"),
                    ],
                )
            ],
            style=style["big_graph"],
        ),
    ]
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
                .filter(user__chapter=chapter, start__lte=end, end__gte=start,)
                .annotate(count=Count("status"))
            )
            majors = dict(
                User.objects.values_list("major__major")
                .filter(
                    chapter=chapter,
                    status__start__lte=end,
                    status__end__gte=start,
                    status__status__in=["active", "activepend", "alumnipend"],
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
                "style": dict(color="#c0392b"),
            }
    align_status = {
        "Actives": ["active", "activepend", "alumnipend"],
        "Inactives": ["away"],
        "Pledges": ["pnm"],
        "Depledges": ["depledge"],
        "Alumni": ["alumni"],
    }
    df = pd.concat(dfs, sort=True)
    for main_status, align_statuss in align_status.items():
        if all([status in df.columns for status in align_statuss]):
            df[main_status] = df[align_statuss].sum(axis=1)
        else:
            df[main_status] = 0
    df["Year Term"] = df.index
    year_terms = [{"label": val, "value": val} for val in df["Year Term"]]
    return (
        df.to_dict(orient="records"),
        year_terms_marks,
        list(year_terms_marks.keys())[0],
        list(year_terms_marks.keys())[-1],
        [list(year_terms_marks.keys())[0], list(year_terms_marks.keys())[-1],],
        year_terms,
        year_terms[-1]["value"],
    )


@app.callback(
    [
        Output("years-text", "children"),
        Output("actives-num", "children"),
        Output("inactives-num", "children"),
        Output("pledges-num", "children"),
        Output("depledges-num", "children"),
        Output("alumni-num", "children"),
    ],
    [Input("chapter-data", "data"), Input("years-slider", "value")],
)
def update_text(data, years, **kwargs):
    statuss = ["Actives", "Inactives", "Pledges", "Depledges", "Alumni"]
    df = pd.DataFrame.from_dict(data)
    if years is None or "year" not in df:
        raise PreventUpdate
    outs = []
    for status in statuss:
        start, end = years
        start_term, end_term = "Spring", "Spring"
        if str(start).endswith(".5"):
            start_term = "Fall"
        if str(end).endswith(".5"):
            end_term = "Fall"
        start_val = df[(df["year"] == int(start)) & (df["term"] == start_term)][
            status
        ].iloc[0]
        end_val = df[(df["year"] == int(end)) & (df["term"] == end_term)][status].iloc[
            0
        ]
        out = fetch_stats(start_val, end_val)
        outs.append(out)
    return (
        f"NOTE: Percent change of member status will result in 'N/A' if value "
        f"at either {years[0]} or {years[1]} is zero.",
        *outs,
    )


@app.callback(
    Output("composition-graph", "figure"),
    [
        Input("chapter-data", "data"),
        Input("years-slider", "value"),
        Input("status-dropdown", "value"),
    ],
    [State("years-slider", "marks"),],
)
def members_graph(data, years, status, year_info, **kwargs):
    df = pd.DataFrame.from_dict(data)
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
        )
        fig.layout.update(showlegend=False, yaxis_title="", xaxis_title="")
    except KeyError:
        raise PreventUpdate
    else:
        return fig


@app.callback(
    Output("majors-graph", "figure"),
    [Input("chapter-data", "data"), Input("years-dropdown", "value")],
)
def majors_graph(data, yearterm, **kwargs):
    df = pd.DataFrame.from_dict(data)
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
        plot_bgcolor="#F9F9F9",
        paper_bgcolor="#F9F9F9",
    )
    return fig


@app.callback(
    Output("gpa-graph", "figure"),
    [Input("chapter-data", "data"), Input("years-slider", "value"),],
    [State("years-slider", "marks")],
)
def gpa_graph(data, years, year_info, **kwargs):
    df = pd.DataFrame.from_dict(data)
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
    )
    fig.layout.update(showlegend=False, yaxis_title="", xaxis_title="")
    return fig


if __name__ == "__main__":
    app.run_server(debug=False)
