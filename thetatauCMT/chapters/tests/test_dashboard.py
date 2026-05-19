"""
Unit tests for thetatauCMT/chapters/dashboard.py.

Covers:
- fetch_stats helper (positive, negative, zero, TypeError)
- layout helper
- PreventUpdate guard branches in each callback
- Happy-path execution of update_text, members_graph, majors_graph, gpa_graph
- load_chapter_data with a real DB user (integration)
"""
import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# fetch_stats
# ---------------------------------------------------------------------------


def test_fetch_stats_positive_change():
    """fetch_stats returns a green H2 with '+..%' when final > initial."""
    from thetatauCMT.chapters.dashboard import fetch_stats

    result = fetch_stats(100, 120)
    result_str = str(result)
    assert "+20.0%" in result_str


def test_fetch_stats_negative_change():
    """fetch_stats returns a red H2 with '-..%' when final < initial."""
    from thetatauCMT.chapters.dashboard import fetch_stats

    result = fetch_stats(100, 80)
    result_str = str(result)
    assert "-20.0%" in result_str


def test_fetch_stats_zero_initial_returns_na():
    """fetch_stats returns 'N/A' when initial is 0 (ZeroDivisionError)."""
    from thetatauCMT.chapters.dashboard import fetch_stats

    result = fetch_stats(0, 10)
    assert "N/A" in str(result)


def test_fetch_stats_none_initial_returns_na():
    """fetch_stats returns 'N/A' when initial is None (TypeError)."""
    from thetatauCMT.chapters.dashboard import fetch_stats

    result = fetch_stats(None, 10)
    assert "N/A" in str(result)


def test_fetch_stats_equal_values_returns_na():
    """fetch_stats returns 'N/A' when there is 0% change."""
    from thetatauCMT.chapters.dashboard import fetch_stats

    result = fetch_stats(50, 50)
    assert "N/A" in str(result)


# ---------------------------------------------------------------------------
# layout helper
# ---------------------------------------------------------------------------


def test_layout_sets_title():
    """layout() updates the figure's title text."""
    import plotly.express as px
    from thetatauCMT.chapters.dashboard import layout

    fig = px.line(x=[2018, 2019], y=[10, 12])
    layout(fig, "Test Chart Title", [2018, 2019])
    assert fig.layout.title.text == "Test Chart Title"


def test_layout_sets_xaxis_ticks():
    """layout() sets tickvals and ticktext on x-axis."""
    import plotly.express as px
    from thetatauCMT.chapters.dashboard import layout

    years = [2019, 2020, 2021]
    fig = px.line(x=years, y=[1, 2, 3])
    layout(fig, "GPA Chart", years)
    # Plotly stores lists as tuples internally
    assert list(fig.layout.xaxis.tickvals) == years
    assert list(fig.layout.xaxis.ticktext) == years


# ---------------------------------------------------------------------------
# update_text — PreventUpdate branches
# ---------------------------------------------------------------------------


def test_update_text_raises_prevent_update_when_years_is_none():
    """update_text raises PreventUpdate when years is None."""
    from dash.exceptions import PreventUpdate
    from thetatauCMT.chapters.dashboard import update_text

    with pytest.raises(PreventUpdate):
        update_text(data={}, years=None)


def test_update_text_raises_prevent_update_when_no_year_column():
    """update_text raises PreventUpdate when 'year' not in DataFrame columns."""
    from dash.exceptions import PreventUpdate
    from thetatauCMT.chapters.dashboard import update_text

    # Empty dict → empty DataFrame → 'year' not in columns
    with pytest.raises(PreventUpdate):
        update_text(data={}, years=[2019, 2019.5])


# ---------------------------------------------------------------------------
# update_text — happy path
# ---------------------------------------------------------------------------


def test_update_text_returns_tuple_with_six_elements():
    """update_text returns (text, H2, H2, H2, H2, H2) for valid inputs."""
    from thetatauCMT.chapters.dashboard import update_text

    data = [
        {
            "year": 2019,
            "term": "Spring",
            "Actives": 10,
            "Aways": 2,
            "PNMs": 3,
            "Depledges": 0,
            "Alumni": 20,
        },
        {
            "year": 2019,
            "term": "Fall",
            "Actives": 12,
            "Aways": 1,
            "PNMs": 5,
            "Depledges": 1,
            "Alumni": 22,
        },
    ]
    years = [2019, 2019.5]  # Spring 2019 → Fall 2019
    result = update_text(data=data, years=years)
    # (years_text, actives_H2, aways_H2, pnms_H2, depledges_H2, alumni_H2)
    assert len(result) == 6
    assert isinstance(result[0], str)
    assert "2019" in result[0]


# ---------------------------------------------------------------------------
# members_graph — PreventUpdate branches
# ---------------------------------------------------------------------------


def test_members_graph_raises_prevent_update_when_year_info_is_none():
    """members_graph raises PreventUpdate when year_info is None."""
    from dash.exceptions import PreventUpdate
    from thetatauCMT.chapters.dashboard import members_graph

    with pytest.raises(PreventUpdate):
        members_graph(
            data=[{"Year Term": "Spring 2019"}],
            years=[2019, 2019.5],
            status=["Actives"],
            year_info=None,
        )


def test_members_graph_raises_prevent_update_when_no_year_term_column():
    """members_graph raises PreventUpdate when 'Year Term' not in DataFrame."""
    from dash.exceptions import PreventUpdate
    from thetatauCMT.chapters.dashboard import members_graph

    with pytest.raises(PreventUpdate):
        members_graph(
            data={},
            years=[2019, 2019.5],
            status=["Actives"],
            year_info={"2019": {"label": "Spring 2019"}},
        )


# ---------------------------------------------------------------------------
# members_graph — happy path
# ---------------------------------------------------------------------------


def test_members_graph_returns_figure():
    """members_graph returns a plotly figure for valid inputs."""
    from thetatauCMT.chapters.dashboard import members_graph

    data = [
        {
            "Year Term": "Spring 2019",
            "Actives": 10,
            "Aways": 2,
            "PNMs": 3,
            "Depledges": 0,
            "Alumni": 20,
        },
        {
            "Year Term": "Fall 2019",
            "Actives": 12,
            "Aways": 1,
            "PNMs": 5,
            "Depledges": 1,
            "Alumni": 22,
        },
    ]
    year_info = {
        "2019": {"label": "Spring 2019"},
        "2019.5": {"label": "Fall 2019"},
    }
    result = members_graph(
        data=data, years=[2019, 2019.5], status=["Actives"], year_info=year_info
    )
    assert result is not None


# ---------------------------------------------------------------------------
# majors_graph — PreventUpdate branch
# ---------------------------------------------------------------------------


def test_majors_graph_raises_prevent_update_on_missing_yearterm():
    """majors_graph raises PreventUpdate when yearterm not found in data."""
    from dash.exceptions import PreventUpdate
    from thetatauCMT.chapters.dashboard import majors_graph

    data = [{"Year Term": "Spring 2019", "majors": {"CS": 5}}]
    with pytest.raises(PreventUpdate):
        majors_graph(data=data, yearterm="Fall 2099")


def test_majors_graph_raises_prevent_update_on_empty_data():
    """majors_graph raises PreventUpdate when data dict is empty."""
    from dash.exceptions import PreventUpdate
    from thetatauCMT.chapters.dashboard import majors_graph

    with pytest.raises(PreventUpdate):
        majors_graph(data={}, yearterm="Spring 2019")


# ---------------------------------------------------------------------------
# majors_graph — happy path
# ---------------------------------------------------------------------------


def test_majors_graph_returns_figure():
    """majors_graph returns a plotly figure for valid inputs."""
    from thetatauCMT.chapters.dashboard import majors_graph

    data = [
        {
            "Year Term": "Spring 2019",
            "majors": {"Computer Science": 10, "Electrical Engineering": 5},
        }
    ]
    result = majors_graph(data=data, yearterm="Spring 2019")
    assert result is not None
    assert result.layout.title.text == "Major of Study Spring 2019"


# ---------------------------------------------------------------------------
# gpa_graph — PreventUpdate branches
# ---------------------------------------------------------------------------


def test_gpa_graph_raises_prevent_update_when_year_info_is_none():
    """gpa_graph raises PreventUpdate when year_info is None."""
    from dash.exceptions import PreventUpdate
    from thetatauCMT.chapters.dashboard import gpa_graph

    with pytest.raises(PreventUpdate):
        gpa_graph(data={}, years=[2019, 2019.5], year_info=None)


def test_gpa_graph_raises_prevent_update_when_no_year_term_column():
    """gpa_graph raises PreventUpdate when 'Year Term' not in DataFrame."""
    from dash.exceptions import PreventUpdate
    from thetatauCMT.chapters.dashboard import gpa_graph

    with pytest.raises(PreventUpdate):
        gpa_graph(
            data={},
            years=[2019, 2019.5],
            year_info={"2019": {"label": "Spring 2019"}},
        )


# ---------------------------------------------------------------------------
# gpa_graph — happy path
# ---------------------------------------------------------------------------


def test_gpa_graph_returns_figure():
    """gpa_graph returns a plotly figure for valid inputs."""
    from thetatauCMT.chapters.dashboard import gpa_graph

    data = [
        {
            "Year Term": "Spring 2019",
            "gpa__avg": 3.1,
            "gpa__count": 5,
        },
        {
            "Year Term": "Fall 2019",
            "gpa__avg": 3.3,
            "gpa__count": 8,
        },
    ]
    year_info = {
        "2019": {"label": "Spring 2019"},
        "2019.5": {"label": "Fall 2019"},
    }
    result = gpa_graph(data=data, years=[2019, 2019.5], year_info=year_info)
    assert result is not None


# ---------------------------------------------------------------------------
# load_chapter_data — integration (requires DB)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_load_chapter_data_returns_seven_outputs(auto_login_user):
    """load_chapter_data returns a 7-tuple for a valid authenticated user."""
    from thetatauCMT.chapters.dashboard import load_chapter_data

    _, user = auto_login_user()
    result = load_chapter_data(1, **{"user": user})
    assert isinstance(result, tuple)
    assert len(result) == 7


@pytest.mark.django_db
def test_load_chapter_data_anonymous_raises_prevent_update(auto_login_user):
    """load_chapter_data raises PreventUpdate when user is anonymous."""
    from dash.exceptions import PreventUpdate
    from django.contrib.auth.models import AnonymousUser
    from thetatauCMT.chapters.dashboard import load_chapter_data

    anon = AnonymousUser()
    with pytest.raises(PreventUpdate):
        load_chapter_data(1, **{"user": anon})


@pytest.mark.django_db
def test_load_chapter_data_first_output_is_list(auto_login_user):
    """The first output of load_chapter_data is a list of dicts (chapter data)."""
    from thetatauCMT.chapters.dashboard import load_chapter_data

    _, user = auto_login_user()
    result = load_chapter_data(1, **{"user": user})
    chapter_data = result[0]
    assert isinstance(chapter_data, list)
