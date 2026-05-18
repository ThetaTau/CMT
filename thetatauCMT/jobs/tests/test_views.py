import pytest
from django.urls import reverse

from thetatauCMT.jobs.tests.test_models import _make_job


@pytest.mark.django_db
def test_job_list_view_authenticated(auto_login_user):
    """Any authenticated user can see the job list."""
    client, user = auto_login_user()
    url = reverse("jobs:list")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_job_list_view_unauthenticated(client):
    url = reverse("jobs:list")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_job_search_list_view_authenticated(auto_login_user):
    client, user = auto_login_user()
    url = reverse("jobs:search")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_job_search_list_view_unauthenticated(client):
    url = reverse("jobs:search")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_job_detail_view_live_job(auto_login_user):
    """A live (published) job is accessible to authenticated users."""
    client, user = auto_login_user()
    job = _make_job()
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_job_detail_view_unauthenticated(client):
    job = _make_job()
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_job_redirect_view(auto_login_user):
    """Redirect view sends authenticated users to the job list."""
    client, user = auto_login_user()
    url = reverse("jobs:redirect")
    response = client.get(url)
    assert response.status_code == 302
    assert "/jobs/" in response["Location"]


@pytest.mark.django_db
def test_job_create_view_authenticated(auto_login_user):
    """Authenticated user can access the job create form.

    The form requires a 'United States' Country entry to exist (used as a
    default initial value). We create it here before exercising the view.
    """
    from address.models import Country
    Country.objects.get_or_create(name="United States")
    client, user = auto_login_user()
    url = reverse("jobs:add")
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_job_create_view_unauthenticated(client):
    url = reverse("jobs:add")
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
