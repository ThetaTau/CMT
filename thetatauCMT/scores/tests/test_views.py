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
