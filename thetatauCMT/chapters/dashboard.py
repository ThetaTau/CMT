import dash
import pandas as pd
import plotly.graph_objects as go
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from django_pandas.io import read_frame

if __name__ == "__main__":
    import os
    import django

    app = dash.Dash(__name__)
    os.chdir("../")
    os.getcwd()
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    django.setup()
else:
    from django_plotly_dash import DjangoDash

    app = DjangoDash("Dashboard")

from chapters.models import Chapter
from users.models import User, UserStatusChange, UserSemesterGPA

## -------------------------------------------------------------------------------
## STYLING ASSETS
## -------------------------------------------------------------------------------

colors = {
    "Actives": "#ff9f43",
    "Inactives": "#a29bfe",
    "Pledges": "#57606f",
    "Depledges": "#d63031",
    "Alumnis": "#2e86de",
    "Fall": "#c0392b",
    "Winter": "#2e86de",
    "Spring": "#fbc531",
    "Summer": "#8c7ae6",
}

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

## -------------------------------------------------------------------------------
## HELPER FUNCTIONS
## -------------------------------------------------------------------------------


def percentage(x, y):
    try:
        return round(x / y * 100)
    except ZeroDivisionError:
        return 0


def get_group(g, key):
    try:
        return len(g.get_group(key))
    except KeyError:
        return 0


def calculateChange(initial, final):
    try:
        return round(((final - initial) / initial * 100), 2)
    except ZeroDivisionError:
        return 0


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


def fetchStats(data, years, status):
    df = pd.DataFrame.from_dict(data)
    date_start = str(years[0]) + "-01-01"
    date_end = str(years[1]) + "-01-01"
    df["start_range"] = (df["start"] <= date_start) & (df["end"] >= date_start)
    df["end_range"] = (df["start"] <= date_end) & (df["end"] >= date_end)
    gb_start = df.groupby(["status", "start_range"])
    gb_end = df.groupby(["status", "end_range"])
    change = calculateChange(
        get_group(gb_start, (status, True)), get_group(gb_end, (status, True))
    )
    if change > 0:
        return html.H2("+{}%".format(change), style=dict(color="#1dd1a1"))
    if change < 0:
        return html.H2("{}%".format(change), style=dict(color="#ff6b6b"))
    else:
        return html.H2("N/A", style=dict(color="#b2bec3"))


## -------------------------------------------------------------------------------

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
                dcc.RangeSlider(
                    id="years-slider",
                    min=2010,
                    max=2021,
                    marks={
                        2010: "2010",
                        2012: "2012",
                        2014: "2014",
                        2016: "2016",
                        2018: "2018",
                        2020: "2020",
                        2022: "2022",
                    },
                    value=[2016, 2020],
                ),
            ],
            style=style["slider"],
        ),
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.H6("Actives", style=dict(color=colors["Actives"])),
                        html.Div(id="actives-num"),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    children=[
                        html.H6("Inactives", style=dict(color=colors["Inactives"])),
                        html.Div(id="inactives-num"),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    children=[
                        html.H6("Pledges", style=dict(color=colors["Pledges"])),
                        html.Div(id="pledges-num"),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    children=[
                        html.H6("Depledges", style=dict(color=colors["Depledges"])),
                        html.Div(id="depledges-num"),
                    ],
                    style=style["number"],
                ),
                html.Div(
                    children=[
                        html.H6("Alumnis", style=dict(color=colors["Alumnis"])),
                        html.Div(id="alumni-num"),
                    ],
                    style=style["number"],
                ),
            ],
            style=dict(display="flex", flexDirection="row"),
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
                        dcc.Loading(
                            type="default",
                            children=[
                                # Graph 2: Number of Actives/Inactives/Pledges Over Time
                                dcc.Graph(id="chapter-size-graph"),
                            ],
                        ),
                    ],
                    style=style["small_graph"],
                ),
                html.Div(
                    children=[
                        dcc.Loading(
                            type="default",
                            children=[
                                # Graph 3: Pledges/Depledges Over Time
                                dcc.Graph(id="retention-graph"),
                            ],
                        ),
                    ],
                    style=style["small_graph"],
                ),
            ],
            style=dict(display="flex", flexDirection="row"),
        ),
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.P("Select year: "),
                        dcc.Dropdown(id="years-dropdown"),
                    ],
                    style=style["small_graph"],
                ),
                html.Div(
                    children=[
                        dcc.Loading(
                            type="default",
                            children=[
                                # Graph 4: Majors of Study
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
                        # Graph 5: Average GPA over time
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
    Output("chapter-data", "data"), [Input("invisible-button", "n_clicks")]
)
def load_chapter_data(clicks, **kwargs):
    user = kwargs.get("user", None)
    chapter = user.current_chapter
    df_user = read_frame(User.objects.filter(chapter=chapter))
    df_status = read_frame(UserStatusChange.objects.filter(user__chapter=chapter))
    df_gpa = read_frame(UserSemesterGPA.objects.filter(user__chapter=chapter))
    if df_user.empty or df_status.empty or df_gpa.empty:
        df = pd.DataFrame()
        # initialize empty dataframe with NA values to prevent error queries when loading empty chapters
        df["start"] = df["end"] = ["0001-01-01"]
        df["status"] = df["major"] = [""]
        return df.to_dict()
    df_user = df_user[["name", "major"]]
    df_status = df_status[["start", "end", "status", "user"]]
    df = pd.merge(
        pd.merge(
            df_user.rename(columns={"name": "user"}), df_status, on="user", how="left"
        ),
        df_gpa,
        on="user",
        how="left",
    )
    print("Load Data")
    return df.to_dict(orient="records")


@app.callback(
    Output("composition-graph", "figure"),
    [Input("chapter-data", "data"), Input("years-slider", "value")],
)
def members_graph(data, years, **kwargs):
    groups = {
        "Actives": [],
        "Inactives": [],
        "Pledges": [],
        "Depledges": [],
        "Alumnis": [],
    }
    YEARS = [str(year) for year in range(years[0], years[1] + 1)]
    df = pd.DataFrame.from_dict(data)
    DataOut = []

    for year in YEARS:
        date = year + "-01-01"
        df["term"] = (df["start"] <= date) & (df["end"] >= date)
        gb = df.groupby(["status", "term"])
        groups["Actives"].append(
            get_group(gb, ("active", True)) + get_group(gb, ("active pending", True))
        )
        groups["Inactives"].append(
            get_group(gb, ("alumni pending", True)) + get_group(gb, ("away", True))
        )
        groups["Pledges"].append(get_group(gb, ("prospective", True)))
        groups["Depledges"].append(get_group(gb, ("depledge", True)))
        groups["Alumnis"].append(get_group(gb, ("alumni", True)))

    TotalMembers = [
        j + k + x + y + z
        for j, k, x, y, z in zip(
            groups["Actives"],
            groups["Inactives"],
            groups["Pledges"],
            groups["Depledges"],
            groups["Alumnis"],
        )
    ]

    for key, value in groups.items():
        percent = [percentage(x, y) for x, y in zip(value, TotalMembers)]
        trace = go.Scatter(
            name=key,
            x=YEARS,
            y=value,
            hovertemplate="<i>Count</i>: %{y}" + "<br>%{text}%</br>",
            text=percent,
            marker=dict(color=colors[key]),
            showlegend=False,
        )
        DataOut.append(trace)

    fig = go.Figure(data=DataOut)
    layout(fig, "Membership Composition", YEARS)
    fig.update_layout(
        updatemenus=[
            dict(
                direction="down",
                showactive=True,
                y=2.0,
                xanchor="left",
                yanchor="top",
                buttons=list(
                    [
                        dict(
                            label="All",
                            method="update",
                            args=[{"visible": [True, True, True, True, True]}],
                        ),
                        dict(
                            label="Actives",
                            method="update",
                            args=[{"visible": [True, False, False, False, False]}],
                        ),
                        dict(
                            label="Inactives",
                            method="update",
                            args=[{"visible": [False, True, False, False, False]}],
                        ),
                        dict(
                            label="Pledges",
                            method="update",
                            args=[{"visible": [False, False, True, False, False]}],
                        ),
                        dict(
                            label="Depledges",
                            method="update",
                            args=[{"visible": [False, False, False, True, False]}],
                        ),
                        dict(
                            label="Alumni",
                            method="update",
                            args=[{"visible": [False, False, False, False, True]}],
                        ),
                    ]
                ),
            )
        ],
    )
    return fig


@app.callback(
    Output("retention-graph", "figure"),
    [Input("chapter-data", "data"), Input("years-slider", "value")],
)
def pledge_depledge_graph(data, years, **kwargs):
    groups = {
        "Pledges": [],
        "Depledges": [],
    }
    YEARS = [str(year) for year in range(years[0], years[1] + 1)]
    df = pd.DataFrame.from_dict(data)
    DataOut = []

    for year in YEARS:
        date = year + "-01-01"
        df["term"] = (df["start"] <= date) & (df["end"] >= date)
        gb = df.groupby(["status", "term"])
        groups["Pledges"].append(get_group(gb, ("prospective", True)))
        groups["Depledges"].append(get_group(gb, ("depledge", True)))

    TotalMembers = [x + y for x, y in zip(groups["Pledges"], groups["Depledges"])]

    for key, value in groups.items():
        percent = [percentage(x, y) for x, y in zip(value, TotalMembers)]
        trace = go.Scatter(
            name=key,
            x=YEARS,
            y=value,
            hovertemplate="<i>Count</i>: %{y}" + "<br>%{text}%</br>",
            text=percent,
            marker=dict(color=colors[key]),
            showlegend=False,
        )
        DataOut.append(trace)

    fig = go.Figure(data=DataOut)
    layout(fig, "Recruitment Retention", YEARS)
    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                active=0,
                xanchor="center",
                x=0.5,
                y=-0.5,
                yanchor="bottom",
                buttons=list(
                    [
                        dict(
                            label="All",
                            method="update",
                            args=[{"visible": [True, True]}],
                        ),
                        dict(
                            label="Pledges",
                            method="update",
                            args=[{"visible": [True, False]}],
                        ),
                        dict(
                            label="Depledges",
                            method="update",
                            args=[{"visible": [False, True]}],
                        ),
                    ]
                ),
            )
        ],
    )

    return fig


@app.callback(
    Output("chapter-size-graph", "figure"),
    [Input("chapter-data", "data"), Input("years-slider", "value"),],
)
def chapter_size_graph(data, years, **kwargs):
    TERMS = {"Fall": [], "Spring": []}
    YEARS = [str(year) for year in range(years[0], years[1] + 1)]
    df = pd.DataFrame.from_dict(data)
    DataOut = []

    for term in TERMS:
        for year in YEARS:
            if term == "Fall":
                date = year + "-12-01"
            if term == "Spring":
                date = year + "-05-01"
            df["term"] = (df["start"] <= date) & (df["end"] >= date)
            gb = df.groupby(["status", "term"])
            TERMS[term].append(
                get_group(gb, ("active", True)) + get_group(gb, ("alumni", True))
            )
        trace = go.Bar(
            name=term,
            x=YEARS,
            y=TERMS[term],
            marker=dict(color=colors[term]),
            showlegend=False,
        )
        DataOut.append(trace)

    fig = go.Figure(data=DataOut)
    layout(fig, "Chapter Size by Semester", YEARS)
    fig.update_layout(barmode="group")
    return fig


@app.callback(Output("years-dropdown", "options"), [Input("years-slider", "value")])
def dropdown(years, **kwargs):
    options = []
    YEARS = [x for x in range(years[0], years[1] + 1)]
    for year in YEARS:
        options.append({"label": str(year), "value": year})
    return options


@app.callback(
    Output("majors-graph", "figure"),
    [Input("chapter-data", "data"), Input("years-dropdown", "value")],
)
def majors_graph(data, year, **kwargs):
    df = pd.DataFrame.from_dict(data)
    MAJORS = set()
    values = []
    date = str(year) + "-01-01"
    df["term"] = (df["start"] <= date) & (df["end"] >= date)
    gb = df.groupby(["major", "status", "term"])
    for name, group in gb:
        MAJORS.add(name[0])

    for major in MAJORS:
        values.append(get_group(gb, (major, "active", True)))

    fig = go.Figure(data=[go.Pie(labels=list(MAJORS), values=values, hole=0.35,)])
    fig.update_layout(
        title={
            "text": "Major of Study (" + str(year) + ")",
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
)
def gpa_graph(data, years, **kwargs):
    YEARS = [x for x in range(years[0], years[1] + 1)]
    TERMS = {"Fall": [], "Winter": [], "Spring": [], "Summer": []}
    df = pd.DataFrame.from_dict(data)
    gb = df.groupby(["term", "year"])
    DataOut = []

    for term in TERMS:
        for year in YEARS:
            TERMS[term].append(gb.get_group((term, str(year)))["gpa"].mean())

    for key, value in TERMS.items():
        trace = go.Scatter(
            name=key,
            x=YEARS,
            y=value,
            hovertemplate="<i>Average</i>: %{y}",
            marker=dict(color=colors[key]),
            showlegend=False,
        )
        DataOut.append(trace)

    fig = go.Figure(data=DataOut)
    layout(fig, "Average GPA", YEARS)
    fig.update_layout(
        yaxis=dict(showgrid=True, gridcolor="#dcdde1", ticks="outside"),
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                active=0,
                xanchor="center",
                x=0.5,
                y=-0.5,
                yanchor="bottom",
                buttons=list(
                    [
                        dict(
                            label="All",
                            method="update",
                            args=[{"visible": [True, True, True, True]}],
                        ),
                        dict(
                            label="Fall",
                            method="update",
                            args=[{"visible": [True, False, False, False]}],
                        ),
                        dict(
                            label="Winter",
                            method="update",
                            args=[{"visible": [False, True, False, False]}],
                        ),
                        dict(
                            label="Spring",
                            method="update",
                            args=[{"visible": [False, False, True, False]}],
                        ),
                        dict(
                            label="Summer",
                            method="update",
                            args=[{"visible": [False, False, False, True]}],
                        ),
                    ]
                ),
            )
        ],
    )
    return fig


@app.callback(
    Output("actives-num", "children"),
    [Input("chapter-data", "data"), Input("years-slider", "value"),],
)
def actives_stats(data, years, **kwargs):
    df = pd.DataFrame.from_dict(data)
    return fetchStats(df, years, "active")


@app.callback(
    Output("inactives-num", "children"),
    [Input("chapter-data", "data"), Input("years-slider", "value"),],
)
def actives_stats(data, years, **kwargs):
    return fetchStats(data, years, "alumni pending")


@app.callback(
    Output("pledges-num", "children"),
    [Input("chapter-data", "data"), Input("years-slider", "value"),],
)
def pledges_stats(data, years, **kwargs):
    return fetchStats(data, years, "prospective")


@app.callback(
    Output("depledges-num", "children"),
    [Input("chapter-data", "data"), Input("years-slider", "value"),],
)
def actives_stats(data, years, **kwargs):
    return fetchStats(data, years, "depledge")


@app.callback(
    Output("alumni-num", "children"),
    [Input("chapter-data", "data"), Input("years-slider", "value"),],
)
def alumni_stats(data, years, **kwargs):
    return fetchStats(data, years, "alumni")


if __name__ == "__main__":
    app.run_server(debug=False)
