import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
from django_pandas.io import read_frame
from dash.exceptions import PreventUpdate

if __name__ == "__main__":
    import dash
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
from users.models import User, UserStatusChange

colors = {
    "Actives": "darkred",
    "Inactives": "grey",
    "Pledges": "green",
    "Depledges": "firebrick",
    "Alumnis": "black",
    "Fall": "#EB8686",
    "Spring": "#E66868",
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


## -------------------------------------------------------------------------------

app.layout = html.Div(
    children=[
        # invisible button for initial loading
        html.Button(id="invisible-button", style={"display": "none"}),
        dcc.Store(id="chapter-data", storage_type="session"),
        html.Div(
            children=[html.H1("Status Dashboard")],
            style=dict(
                display="flex", flexDirection="row", marginBottom=10, marginTop=20
            ),
        ),
        html.Div(
            children=[
                html.Div(
                    children=[
                        html.P("Select semester:"),
                        dcc.Dropdown(
                            id="semester-dropdown",
                            options=[
                                {"label": "Fall", "value": 1},
                                {"label": "Spring", "value": 2},
                            ],
                            value=1,
                        ),
                        html.Div(
                            children=[
                                html.P("Select date range:", style=dict(marginTop=15),),
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
                                    },
                                    value=[2014, 2020],
                                ),
                            ],
                            style=dict(padding=8, margin=0),
                        ),
                        html.Div(
                            children=[
                                html.H5(
                                    "Chapter size breakdown for selected date range"
                                )
                            ],
                            style=dict(marginTop=60, textAlign="center"),
                        ),
                        html.Div(
                            children=[
                                html.Div(
                                    [html.H4(id="actives-num"), html.H6("Actives")],
                                    id="actives",
                                    style=dict(
                                        borderRadius=5,
                                        backgroundColor="#fcd781",
                                        margin=10,
                                        padding=15,
                                        position="relative",
                                        boxShadow="2px 2px 2px lightgrey",
                                        display="flex",
                                        flexDirection="column",
                                        textAlign="center",
                                    ),
                                ),
                                html.Div(
                                    [html.H4(id="alumni-num"), html.H6("Alumnis"),],
                                    id="alumni",
                                    style=dict(
                                        borderRadius=5,
                                        backgroundColor="rgba(168,7,7,0.6)",
                                        margin=10,
                                        padding=15,
                                        position="relative",
                                        boxShadow="2px 2px 2px lightgrey",
                                        display="flex",
                                        flexDirection="column",
                                        textAlign="center",
                                    ),
                                ),
                            ],
                            style=dict(
                                display="flex",
                                flexDirection="row",
                                marginTop=10,
                                marginLeft=50,
                            ),
                        ),
                    ],
                    style=dict(
                        borderRadius=5,
                        backgroundColor="#f9f9f9",
                        margin=10,
                        padding=15,
                        width="30.6666666667%",
                        position="relative",
                        boxShadow="2px 2px 2px lightgrey",
                    ),
                ),
                # Graph 1: Chapter Size by Semester Over Time
                html.Div(
                    children=[dcc.Graph(id="chapter-size-graph"),],
                    style=dict(
                        borderRadius=5,
                        backgroundColor="#f9f9f9",
                        margin=10,
                        padding=15,
                        width="65.3333333333%",
                        position="relative",
                        boxShadow="2px 2px 2px lightgrey",
                    ),
                ),
            ],
            style=dict(display="flex", flexDirection="row"),
        ),
        html.Div(
            children=[
                # Graph 2: Number of Actives/Inactives/Pledges Over Time
                html.Div(
                    children=[dcc.Graph(id="composition-graph"),],
                    style=dict(
                        borderRadius=5,
                        backgroundColor="#f9f9f9",
                        margin=10,
                        padding=15,
                        width="48%",
                        position="relative",
                        boxShadow="2px 2px 2px lightgrey",
                    ),
                ),
                # Graph 3: Pledges/Depledges Over Time
                html.Div(
                    children=[dcc.Graph(id="retention-graph"),],
                    style=dict(
                        borderRadius=5,
                        backgroundColor="#f9f9f9",
                        margin=10,
                        padding=15,
                        width="48%",
                        position="relative",
                        boxShadow="2px 2px 2px lightgrey",
                    ),
                ),
            ],
            style=dict(display="flex", flexDirection="row"),
        ),
    ]
)

# invisible button
@app.expanded_callback(
    Output("chapter-data", "data"), [Input("invisible-button", "n_clicks")]
)
def load_data(clicks, **kwargs):
    user = kwargs.get("user", None)
    chapter = user.current_chapter
    df = read_frame(UserStatusChange.objects.filter(user__chapter=chapter))
    df = df[["start", "end", "status"]]
    if df.empty:
        raise PreventUpdate
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
    }
    YEARS = [str(year) for year in range(years[0], years[1] + 1)]
    df = pd.DataFrame.from_dict(data)
    DataOut = []

    for year in YEARS:
        date = year + "-01-01"
        df["term"] = (df["start"] <= date) & (df["end"] >= date)
        gb = df.groupby(["status", "term"])
        groups["Actives"].append(get_group(gb, ("active", True)))
        groups["Inactives"].append(get_group(gb, ("away", True)))
        groups["Pledges"].append(get_group(gb, ("prospective", True)))

    TotalMembers = [
        x + y + z
        for x, y, z in zip(groups["Actives"], groups["Inactives"], groups["Pledges"])
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

    fig.update_layout(
        title={
            "text": "Membership Composition",
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
        updatemenus=[
            dict(
                type="buttons",
                direction="down",
                active=0,
                x=0.1,
                y=1.0,
                buttons=list(
                    [
                        dict(
                            label="All",
                            method="update",
                            args=[{"visible": [True, True, True]}],
                        ),
                        dict(
                            label="Actives",
                            method="update",
                            args=[{"visible": [True, False, False]}],
                        ),
                        dict(
                            label="Inactives",
                            method="update",
                            args=[{"visible": [False, True, False]}],
                        ),
                        dict(
                            label="Pledges",
                            method="update",
                            args=[{"visible": [False, False, True]}],
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

    fig.update_layout(
        title={
            "text": "Recruitment Retention",
            "x": 0.5,
            "y": 0.9,
            "font": dict(family="Arial", size=22),
            "xanchor": "center",
            "yanchor": "top",
        },
        plot_bgcolor="#F9F9F9",
        paper_bgcolor="#F9F9F9",
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
        updatemenus=[
            dict(
                type="buttons",
                direction="down",
                active=0,
                x=0.1,
                y=1.0,
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
    groups = {"Fall": [], "Spring": []}
    YEARS = [str(year) for year in range(years[0], years[1] + 1)]
    df = pd.DataFrame.from_dict(data)
    DataOut = []

    for key, value in groups.items():
        for year in YEARS:
            if key == "Fall":
                date = year + "-12-01"
            if key == "Spring":
                date = year + "-05-01"
            df["term"] = (df["start"] <= date) & (df["end"] >= date)
            gb = df.groupby(["status", "term"])
            groups[key].append(
                get_group(gb, ("active", True)) + get_group(gb, ("alumni", True))
            )
        trace = go.Bar(
            name=key,
            x=YEARS,
            y=value,
            marker=dict(color=colors[key]),
            showlegend=False,
        )
        DataOut.append(trace)

    fig = go.Figure(data=DataOut)

    fig.update_layout(
        barmode="group",
        title={
            "text": "Chapter Size by Semester",
            "x": 0.5,
            "y": 0.9,
            "xanchor": "center",
            "yanchor": "top",
        },
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showline=False,
            ticktext=YEARS,
            tickvals=YEARS,
        ),
        yaxis=dict(
            showgrid=False, zeroline=False, showline=False, showticklabels=False
        ),
        plot_bgcolor="#F9F9F9",
        paper_bgcolor="#F9F9F9",
    )
    return fig


@app.callback(
    Output("actives-num", "children"),
    [
        Input("chapter-data", "data"),
        Input("semester-dropdown", "value"),
        Input("years-slider", "value"),
    ],
)
def update_actives_num(data, semester, years_slider, **kwargs):
    if semester == 1:
        date_str = "-12-01"
    if semester == 2:
        date_str = "-05-01"

    total = 0
    df = pd.DataFrame.from_dict(data)
    for i in range(years_slider[0], years_slider[1] + 1):
        date = str(i) + date_str
        df["term"] = (df["start"] <= date) & (df["end"] >= date)
        gb = df.groupby(["status", "term"])
        total += get_group(gb, ("active", True))

    return total


@app.callback(
    Output("alumni-num", "children"),
    [
        Input("chapter-data", "data"),
        Input("semester-dropdown", "value"),
        Input("years-slider", "value"),
    ],
)
def update_alumni_num(data, semester, years_slider, **kwargs):
    if semester == 1:
        date_str = "-12-01"
    if semester == 2:
        date_str = "-05-01"

    total = 0
    df = pd.DataFrame.from_dict(data)
    for i in range(years_slider[0], years_slider[1] + 1):
        date = str(i) + date_str
        df["term"] = (df["start"] <= date) & (df["end"] >= date)
        gb = df.groupby(["status", "term"])
        total += get_group(gb, ("alumni", True))

    return total


if __name__ == "__main__":
    app.run_server(debug=False)
