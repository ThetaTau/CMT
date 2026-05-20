import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_training_list_view_authenticated(auto_login_user):
    """Authenticated user can see their training list."""
    client, user = auto_login_user()
    url = reverse("trainings:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_training_list_view_unauthenticated(client):
    url = reverse("trainings:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
