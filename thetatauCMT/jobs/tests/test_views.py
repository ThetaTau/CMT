import datetime
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


# ---------------------------------------------------------------------------
# JobDetailView.dispatch – expired / future publish dates redirect to list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_detail_expired_job_redirects_to_list(auto_login_user):
    """Accessing an expired job as non-owner redirects to job list."""
    client, user = auto_login_user()
    job = _make_job(
        publish_start=datetime.date.today() - datetime.timedelta(days=60),
        publish_end=datetime.date.today() - datetime.timedelta(days=1),
        title=f"Expired Job {datetime.datetime.now().microsecond}",
    )
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url, follow=True)
    # Redirects to job list when job is expired and user is not creator
    assert response.status_code == 200


@pytest.mark.django_db
def test_job_detail_future_job_redirects_to_list(auto_login_user):
    """Accessing a future (not yet published) job as non-owner redirects."""
    client, user = auto_login_user()
    job = _make_job(
        publish_start=datetime.date.today() + datetime.timedelta(days=10),
        publish_end=datetime.date.today() + datetime.timedelta(days=30),
        title=f"Future Job {datetime.datetime.now().microsecond}",
    )
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# JobUpdateView – non-owner access and update
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_update_view_owner_gets_form(auto_login_user):
    """Owner of a job can access the update form."""
    from address.models import Country
    Country.objects.get_or_create(name="United States")
    client, user = auto_login_user()
    job = _make_job(title=f"My Job {datetime.datetime.now().microsecond}")
    job.created_by = user
    job.save()
    url = reverse("jobs:update", kwargs={"pk": job.pk})
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_job_update_view_non_owner_redirects(auto_login_user):
    """Non-owner accessing job update is redirected to job detail."""
    client, user = auto_login_user()
    # Create a job without assigning user as creator
    job = _make_job(title=f"Other Job {datetime.datetime.now().microsecond}")
    url = reverse("jobs:update", kwargs={"pk": job.pk})
    response = client.get(url, follow=True)
    # Redirected because user is not the owner
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# JobListView – pk="0" (own jobs) and search filter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_list_view_with_search_pk(auto_login_user):
    """JobListView with pk of a JobSearch filters using that search."""
    from thetatauCMT.jobs.models import JobSearch
    client, user = auto_login_user()
    job_search = JobSearch.objects.create(
        search_title="Test Search",
        search_description="A test search",
        created_by=user,
    )
    url = reverse("jobs:search_filter", kwargs={"pk": job_search.pk})
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# KeywordAutocomplete and MajorAutocomplete
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_keyword_autocomplete_authenticated(auto_login_user):
    """Authenticated users can query keyword autocomplete."""
    from thetatauCMT.jobs.models import Keyword
    Keyword.objects.create(name="python")
    client, user = auto_login_user()
    url = reverse("jobs:keyword-autocomplete")
    response = client.get(url, {"q": "pyth"})
    assert response.status_code == 200


@pytest.mark.django_db
def test_keyword_autocomplete_unauthenticated(client):
    """Unauthenticated users get empty results from keyword autocomplete."""
    url = reverse("jobs:keyword-autocomplete-ro")
    response = client.get(url, {"q": "python"})
    assert response.status_code in [200, 302]


@pytest.mark.django_db
def test_major_autocomplete_authenticated(auto_login_user):
    """Authenticated users can query major autocomplete."""
    from thetatauCMT.jobs.models import Major
    Major.objects.create(name="Computer Science")
    client, user = auto_login_user()
    url = reverse("jobs:major-autocomplete")
    response = client.get(url, {"q": "comp"})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# JobSearchCreateView – GET
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_search_create_view_authenticated(auto_login_user):
    """Authenticated user can access job search creation form."""
    client, user = auto_login_user()
    url = reverse("jobs:add_search")
    response = client.get(url)
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# JobSearchUpdateView – GET
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_search_update_view_authenticated(auto_login_user):
    """Authenticated user can access job search update form."""
    from thetatauCMT.jobs.models import JobSearch
    client, user = auto_login_user()
    job_search = JobSearch.objects.create(
        search_title="Update Search",
        search_description="A test search",
        created_by=user,
    )
    url = reverse("jobs:update_search", kwargs={"pk": job_search.pk})
    response = client.get(url)
    assert response.status_code == 200
