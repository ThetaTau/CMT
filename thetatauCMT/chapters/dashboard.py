import dash
import datetime
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
from users.models import (
    User,
    UserStatusChange,
    UserSemesterGPA,
    UserSemesterServiceHours,
)

## -------------------------------------------------------------------------------
## STYLING ASSETS
## -------------------------------------------------------------------------------

colors = {
    "Actives": "#ff9f43",
    "Inactives": "#a29bfe",
    "Pledges": "#57606f",
    "Depledges": "#d63031",
    "Alumnis": "#2e86de",
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
        # create set of unique users
        users = set()
        group = pd.DataFrame(g.get_group(key))
        for ind in group.index:
            users.add((group["user"][ind]))
        return len(users)
    except KeyError:
        return 0


def get_term_average(g, key, topic):
    try:
        return g.get_group(key)[topic].mean()
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
    if status == "active":
        change = calculateChange(
            (
                get_group(gb_start, ("active", True))
                + get_group(gb_start, ("active pending", True))
            ),
            (
                get_group(gb_end, ("active", True))
                + get_group(gb_end, ("active pending", True))
            ),
        )
    elif status == "inactive":
        change = calculateChange(
            (
                get_group(gb_start, ("away", True))
                + get_group(gb_start, ("alumni pending", True))
            ),
            (
                get_group(gb_end, ("away", True))
                + get_group(gb_end, ("alumni pending", True))
            ),
        )
    else:
        change = calculateChange(
            get_group(gb_start, (status, True)), get_group(gb_end, (status, True))
        )
    if change > 0:
        return html.H2(
            "+{}%".format(change), style=dict(color="#20bf6b", textAlign="center")
        )
    if change < 0:
        return html.H2(
            "{}%".format(change), style=dict(color="#ff6b6b", textAlign="center")
        )
    else:
        return html.H2("N/A", style=dict(color="#b2bec3", textAlign="center"))


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
                    min=min(YEARS),
                    max=max(YEARS),
                    dots=True,
                    marks={
                        str(year): {"label": str(year), "style": dict(color="#c0392b")}
                        for year in YEARS
                    },
                    value=[2018, now.year],
                ),
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
                        {"label": "Alumnis", "value": "Alumnis"},
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
                            style=dict(color=colors["Actives"], textAlign="center"),
                        ),
                        html.H6(
                            "[ activepend + active ]",
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
                            style=dict(color=colors["Inactives"], textAlign="center"),
                        ),
                        html.H6(
                            "[ alumnipend + away ]",
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
                            style=dict(color=colors["Pledges"], textAlign="center"),
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
                            style=dict(color=colors["Depledges"], textAlign="center"),
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
                            "Alumnis",
                            style=dict(color=colors["Alumnis"], textAlign="center"),
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
                dcc.Loading(
                    type="default",
                    children=[
                        # Graph 2: Number of Actives/Inactives/Pledges Over Time
                        dcc.Graph(id="chapter-size-graph"),
                    ],
                ),
            ],
            style=style["big_graph"],
        ),
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
        # html.Div(
        #     children=[
        #         ),
        #         # html.Div(
        #         #     children=[
        #         #         dcc.Loading(
        #         #             type="default",
        #         #             children=[
        #         #                 # Graph 5: Service Hours over time
        #         #                 dcc.Graph(id="servicehours-graph"),
        #         #             ],
        #         #         )
        #         #     ],
        #         #     style=style["small_graph"],
        #         # ),
        #     ],
        #     style=dict(display="flex", flexDirection="row"),
        # ),
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
    df_gpa = read_frame(UserSemesterGPA.objects.filter(user__chapter=chapter)).rename(
        columns={"term": "gpa_term", "year": "gpa_year"}
    )
    # df_servicehours = read_frame(
    #     UserSemesterServiceHours.objects.filter(user__chapter=chapter)
    # ).rename(columns={"term": "servicehours_term", "year": "servicehours_year"})
    if df_user.empty or df_status.empty or df_gpa.empty:
        df = pd.DataFrame()
        # initialize empty dataframe with NA values to prevent error queries when loading empty chapters
        df["start"] = df["end"] = ["0001-01-01"]
        df["status"] = df["major"] = df["gpa_term"] = df["gpa_year"] = [""]
        return df.to_dict()
    df_user = df_user[["name", "major"]]
    df_status = df_status[["start", "end", "status", "user"]]
    df = pd.merge(
        pd.merge(
            df_user.rename(columns={"name": "user"}), df_status, on="user", how="left",
        ),
        df_gpa,
        on="user",
        how="left",
    )
    print(df)
    print("Load Data")
    return df.to_dict(orient="records")


@app.callback(Output("years-text", "children"), [Input("years-slider", "value")])
def update_text(value, **kwargs):
    return "NOTE: Percent change of member status will result in 'N/A' if value at either {0} or {1} is zero.".format(
        value[0], value[1]
    )


@app.callback(
    Output("composition-graph", "figure"),
    [
        Input("chapter-data", "data"),
        Input("years-slider", "value"),
        Input("status-dropdown", "value"),
    ],
)
def members_graph(data, years, status, **kwargs):
    YEARS = [str(year) for year in range(years[0], years[1] + 1)]
    df = pd.DataFrame.from_dict(data)
    query = {
        "Actives": ["active", "active pending"],
        "Inactives": ["alumni pending", "away"],
        "Pledges": ["prospective"],
        "Depledges": ["depledge"],
        "Alumnis": ["alumni"],
    }
    DataOut = []

    for s in status:
        data = []
        for year in YEARS:
            date = year + "-01-01"
            df["term"] = (df["start"] <= date) & (df["end"] >= date)
            gb = df.groupby(["status", "term"])
            total = 0
            for q in query[s]:
                total += get_group(gb, (q, True))
            data.append(total)
        trace = go.Scatter(
            name=s,
            x=YEARS,
            y=data,
            hovertemplate="<i>Count</i>: %{y}",
            marker=dict(color=colors[s]),
            showlegend=False,
        )
        DataOut.append(trace)

    fig = go.Figure(data=DataOut)
    layout(fig, "Membership Composition", YEARS)
    fig.update_layout(
        xaxis_title="*Members count as measured on January 1st of each year"
    )
    return fig


@app.callback(
    Output("chapter-size-graph", "figure"),
    [Input("chapter-data", "data"), Input("years-slider", "value"),],
)
def chapter_size_graph(data, years, **kwargs):
    YEARS = [str(year) for year in range(years[0], years[1] + 1)]
    academic_terms = []
    for i in range(len(YEARS) - 1):
        academic_terms.append("-".join(YEARS[i : i + 2]))
    df = pd.DataFrame.from_dict(data)
    DataOut = []
    Fall = []
    Spring = []
    for term in academic_terms:
        fall = term[:4] + "-01-01"
        spring = term[5:] + "-06-01"
        df["fall_term"] = (df["start"] <= fall) & (df["end"] >= fall)
        df["spring_term"] = (df["start"] <= spring) & (df["end"] >= spring)
        gb = df.groupby(["status", "fall_term"])
        Fall.append(
            get_group(gb, ("active", True)) + get_group(gb, ("active pending", True))
        )
        gb = df.groupby(["status", "spring_term"])
        Spring.append(
            get_group(gb, ("active", True)) + get_group(gb, ("active pending", True))
        )
    trace = go.Bar(
        name="Fall",
        x=academic_terms,
        y=Fall,
        marker=dict(color=colors["Fall"]),
        showlegend=True,
    )
    DataOut.append(trace)
    trace = go.Bar(
        name="Spring",
        x=academic_terms,
        y=Spring,
        marker=dict(color=colors["Spring"]),
        showlegend=True,
    )
    DataOut.append(trace)
    fig = go.Figure(data=DataOut)
    layout(fig, "Chapter Size per Academic Term", academic_terms)
    fig.update_layout(
        barmode="group",
        xaxis_title="*Fall measured as of January 1st; Spring measured as of June 1st (count includes active/activepend status)",
    )
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
        major = name[0]
        # only add major if group size is greater than 0
        if get_group(gb, (major, "active", True)) != 0:
            MAJORS.add(major)
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
    gb = df.groupby(["gpa_term", "gpa_year"])
    DataOut = []

    for term in TERMS:
        for year in YEARS:
            TERMS[term].append(get_term_average(gb, (term, str(year)), "gpa"))

    for key, value in TERMS.items():
        trace = go.Scatter(
            name=key,
            x=YEARS,
            y=value,
            hovertemplate="<i>Average</i>: %{y}",
            marker=dict(color=colors[key]),
            showlegend=True,
        )
        DataOut.append(trace)

    fig = go.Figure(data=DataOut)
    layout(fig, "Average GPA", YEARS)
    fig.update_layout(yaxis=dict(showgrid=True, gridcolor="#dcdde1", ticks="outside"))
    return fig


# @app.callback(
#     Output("servicehours-graph", "figure"),
#     [Input("chapter-data", "data"), Input("years-slider", "value"),],
# )
# def servicehours_graph(data, years, **kwargs):
#     YEARS = [x for x in range(years[0], years[1] + 1)]
#     TERMS = {"Fall": [], "Winter": [], "Spring": [], "Summer": []}
#     df = pd.DataFrame.from_dict(data)
#     gb = df.groupby(["servicehours_term", "servicehours_year"])
#     DataOut = []

#     for term in TERMS:
#         for year in YEARS:
#             TERMS[term].append(get_term_average(gb, (term, str(year)), "service_hours"))

#     for key, value in TERMS.items():
#         trace = go.Scatter(
#             name=key,
#             x=YEARS,
#             y=value,
#             hovertemplate="<i>Average</i>: %{y}",
#             marker=dict(color=colors[key]),
#             showlegend=True,
#         )
#         DataOut.append(trace)

#     fig = go.Figure(data=DataOut)
#     layout(fig, "Average Service Hours", YEARS)
#     fig.update_layout(yaxis=dict(showgrid=True, gridcolor="#dcdde1", ticks="outside"))
#     return fig


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
def inactives_stats(data, years, **kwargs):
    return fetchStats(data, years, "inactive")


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
