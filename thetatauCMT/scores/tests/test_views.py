import pytest
from django.urls import reverse

from thetatauCMT.scores.models import ScoreType


@pytest.mark.django_db
def test_score_list_view_authenticated(auto_login_user):
    """Any authenticated user can see the score list."""
    client, user = auto_login_user()
    url = reverse("scores:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_score_list_view_unauthenticated(client):
    url = reverse("scores:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_chapter_score_list_view_authenticated(auto_login_user):
    """Any authenticated user can see the chapter score list."""
    client, user = auto_login_user()
    url = reverse("scores:chapterlist")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_chapter_score_list_view_unauthenticated(client):
    url = reverse("scores:chapterlist")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_score_detail_view_authenticated(auto_login_user):
    """Any authenticated user can see a ScoreType detail page."""
    score_type = ScoreType.objects.first()
    if score_type is None:
        pytest.skip("No ScoreType in DB (scoretypes.json fixture not loaded)")
    client, user = auto_login_user()
    url = reverse("scores:detail", kwargs={"slug": score_type.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_score_detail_view_unauthenticated(auto_login_user):
    """Unauthenticated requests to detail view are redirected to login."""
    score_type = ScoreType.objects.first()
    if score_type is None:
        pytest.skip("No ScoreType in DB (scoretypes.json fixture not loaded)")
    client, user = auto_login_user()
    client.logout()
    url = reverse("scores:detail", kwargs={"slug": score_type.slug})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


def test_filter_score_rows_by_total_min():
    """A min bound drops rows whose total is below it."""
    from thetatauCMT.scores.views import filter_score_rows_by_total

    rows = [{"total": 10}, {"total": 50}, {"total": 90}]
    result = filter_score_rows_by_total(rows, "50", None)
    assert [row["total"] for row in result] == [50, 90]


def test_filter_score_rows_by_total_max():
    """A max bound drops rows whose total is above it."""
    from thetatauCMT.scores.views import filter_score_rows_by_total

    rows = [{"total": 10}, {"total": 50}, {"total": 90}]
    result = filter_score_rows_by_total(rows, None, "50")
    assert [row["total"] for row in result] == [10, 50]


def test_filter_score_rows_by_total_range():
    """Combining bounds keeps only rows inside the window."""
    from thetatauCMT.scores.views import filter_score_rows_by_total

    rows = [{"total": 10}, {"total": 50}, {"total": 90}]
    result = filter_score_rows_by_total(rows, "20", "80")
    assert [row["total"] for row in result] == [50]


def test_filter_score_rows_by_total_ignores_blank_and_nonnumeric():
    """Blank or non-numeric bounds leave the rows unchanged."""
    from thetatauCMT.scores.views import filter_score_rows_by_total

    rows = [{"total": 10}, {"total": 90}]
    assert filter_score_rows_by_total(rows, "", None) == rows
    assert filter_score_rows_by_total(rows, "abc", "xyz") == rows


@pytest.mark.django_db
def test_chapter_score_list_view_accepts_score_filter_params(auto_login_user):
    """The chapter score list renders when score_min/score_max are supplied."""
    client, user = auto_login_user()
    url = reverse("scores:chapterlist")
    response = client.get(url, {"score_min": "10", "score_max": "100"})
    assert response.status_code == 200
