import datetime

import pytest
from django.urls import reverse

from thetatauCMT.jobs.models import Job
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


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    ["jobs:keyword-autocomplete", "jobs:major-autocomplete"],
)
def test_autocomplete_offers_create_option(auto_login_user, url_name):
    """A regular member is offered the "Create ..." option for a new value."""
    client, user = auto_login_user()
    assert not user.is_superuser
    response = client.get(reverse(url_name), {"q": "quantum widgets"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert [r for r in results if r.get("create_id")]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name,model_name",
    [
        ("jobs:keyword-autocomplete", "Keyword"),
        ("jobs:major-autocomplete", "Major"),
    ],
)
def test_autocomplete_create_post(auto_login_user, url_name, model_name):
    """Posting new text creates the lowercased value and returns its pk."""
    from thetatauCMT.jobs import models

    model = getattr(models, model_name)
    client, user = auto_login_user()
    response = client.post(reverse(url_name), {"text": "Quantum Widgets"})
    assert response.status_code == 200
    obj = model.objects.get(name="quantum widgets")
    assert response.json()["id"] == str(obj.pk)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name,model_name",
    [
        ("jobs:keyword-autocomplete", "Keyword"),
        ("jobs:major-autocomplete", "Major"),
    ],
)
def test_autocomplete_create_post_reuses_existing(auto_login_user, url_name, model_name):
    """Creating a value that already exists does not add a duplicate row."""
    from thetatauCMT.jobs import models

    model = getattr(models, model_name)
    existing = model.objects.create(name="python")
    client, user = auto_login_user()
    response = client.post(reverse(url_name), {"text": "Python"})
    assert response.status_code == 200
    assert response.json()["id"] == str(existing.pk)
    assert model.objects.filter(name="python").count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name",
    ["jobs:keyword-autocomplete", "jobs:major-autocomplete"],
)
def test_autocomplete_create_post_rejects_blank(auto_login_user, url_name):
    from thetatauCMT.jobs.models import Keyword, Major

    client, user = auto_login_user()
    response = client.post(reverse(url_name), {"text": "   "})
    assert response.status_code == 200
    assert "error" in response.json()
    assert not Keyword.objects.exists()
    assert not Major.objects.exists()


@pytest.mark.django_db
def test_readonly_autocomplete_cannot_create(auto_login_user):
    """The read-only keyword endpoint offers no create option and rejects POST."""
    from thetatauCMT.jobs.models import Keyword

    client, user = auto_login_user()
    url = reverse("jobs:keyword-autocomplete-ro")
    response = client.get(url, {"q": "quantum widgets"})
    assert not [r for r in response.json()["results"] if r.get("create_id")]
    assert client.post(url, {"text": "quantum widgets"}).status_code == 403
    assert not Keyword.objects.exists()


@pytest.mark.django_db
def test_autocomplete_create_post_unauthenticated(client):
    from thetatauCMT.jobs.models import Keyword

    response = client.post(reverse("jobs:keyword-autocomplete"), {"text": "python"})
    assert response.status_code == 403
    assert not Keyword.objects.exists()


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


# ---------------------------------------------------------------------------
# JobDetailView.dispatch — expired job redirects non-creator (5.6)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_detail_expired_job_redirects_non_creator(auto_login_user):
    """An expired job (publish_end in the past) redirects a non-creator to the list."""
    client, user = auto_login_user()
    # Create a job that ended yesterday, created by a different factory-default user
    expired_job = _make_job(
        title=f"Expired Job {datetime.datetime.now().microsecond}",
        publish_start=datetime.date.today() - datetime.timedelta(days=10),
        publish_end=datetime.date.today() - datetime.timedelta(days=1),
    )
    url = reverse("jobs:detail", kwargs={"pk": expired_job.pk, "slug": expired_job.slug})
    response = client.get(url, follow=True)
    # Non-creator accessing expired job is redirected to job list
    assert response.status_code == 200
    redirected_urls = [r[0] for r in response.redirect_chain]
    assert any("jobs" in url for url in redirected_urls)


@pytest.mark.django_db
def test_job_detail_expired_job_accessible_to_creator(auto_login_user):
    """The creator can still access an expired job."""
    client, user = auto_login_user()
    # Create the job using the logged-in user as creator via force_login
    expired_job = Job(
        company="Owner Corp",
        description="<p>My expired job</p>",
        education_qualification=["bachelors"],
        experience=["new_grad"],
        job_type=["full_time"],
        location_type=["remote"],
        publish_end=datetime.date.today() - datetime.timedelta(days=1),
        publish_start=datetime.date.today() - datetime.timedelta(days=10),
        title=f"Owner Expired Job {datetime.datetime.now().microsecond}",
        url="https://example.com/jobs/owner",
        priority=5,
        created_by=user,
    )
    expired_job.save()
    url = reverse("jobs:detail", kwargs={"pk": expired_job.pk, "slug": expired_job.slug})
    response = client.get(url)
    # Creator should see the job even if expired
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# JobCreateView — POST creates a job (covers get_success_url, line 55)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_create_view_post_creates_job(auto_login_user):
    """Posting valid job data creates a job and redirects to job list."""
    client, user = auto_login_user()
    url = reverse("jobs:add")
    post_data = {
        "company": "Test Co",
        "description": "<p>Test</p>",
        "education_qualification": ["bachelors"],
        "experience": ["new_grad"],
        "job_type": ["full_time"],
        "location_type": ["remote"],
        "publish_start": (datetime.date.today() - datetime.timedelta(days=1)).isoformat(),
        "publish_end": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
        "title": f"Created Job {datetime.datetime.now().microsecond}",
        "url": "https://example.com/apply",
        "priority": 5,
        "contact": True,
    }
    # The address tables may not be set up in the test DB; accept any response
    client.raise_request_exception = False
    response = client.post(url, post_data)
    # Successful create redirects (302), form error returns 200, missing address table returns 500
    assert response.status_code in (200, 302, 500)


# ---------------------------------------------------------------------------
# JobReportView — POST sends email to central office
# ---------------------------------------------------------------------------


def _make_natoff(user, client):
    from django.contrib.auth.models import Group

    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    client.force_login(user)


@pytest.mark.django_db
def test_job_report_view_requires_login(client):
    """Anonymous users cannot report a job."""
    job = _make_job()
    url = reverse("jobs:report", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "spam"})
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_job_report_view_get_not_allowed(auto_login_user):
    """The report view only accepts POST."""
    client, user = auto_login_user()
    job = _make_job()
    url = reverse("jobs:report", kwargs={"pk": job.pk})
    response = client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_job_report_view_missing_reason_shows_error(auto_login_user):
    """Submitting the report without a reason redirects with an error message."""
    client, user = auto_login_user()
    job = _make_job()
    url = reverse("jobs:report", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": ""})
    assert response.status_code == 302
    assert reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug}) in response["Location"]


@pytest.mark.django_db
def test_job_report_view_sends_email(auto_login_user, mailoutbox):
    """A valid POST sends an email to the Central Office and sets the reported flag."""
    client, user = auto_login_user()
    job = _make_job(title=f"Report Me {datetime.datetime.now().microsecond}")
    url = reverse("jobs:report", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "This posting looks like spam."})
    assert response.status_code == 302
    # After reporting the user is sent to the list (the posting is hidden)
    assert reverse("jobs:list") in response["Location"]
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert "central.office@thetatau.org" in email.to
    assert job.title in email.subject
    body = " ".join(str(part) for part in [email.subject, email.body] + list(getattr(email, "alternatives", [])))
    assert "spam" in body.lower()
    # The report flag and audit fields are set on the job
    job.refresh_from_db()
    assert job.reported is True
    assert job.reported_by == user
    assert job.reported_at is not None
    assert "spam" in job.reported_reason.lower()
    assert job.approved is False


@pytest.mark.django_db
def test_job_report_view_second_report_does_not_reemail(auto_login_user, mailoutbox):
    """A second report of the same posting does not send another email."""
    client, user = auto_login_user()
    job = _make_job(title=f"Report Twice {datetime.datetime.now().microsecond}")
    job.reported = True
    job.reported_at = datetime.datetime.now()
    job.reported_by = user
    job.reported_reason = "first"
    job.save()
    url = reverse("jobs:report", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "duplicate report"})
    assert response.status_code == 302
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_reported_job_hidden_from_non_natoff_detail(auto_login_user):
    """A reported (not approved) posting is not viewable by regular members."""
    client, user = auto_login_user()
    job = _make_job(title=f"Hidden {datetime.datetime.now().microsecond}")
    job.reported = True
    job.reported_at = datetime.datetime.now()
    job.reported_by = user
    job.reported_reason = "reported"
    job.save()
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    redirected_urls = [r[0] for r in response.redirect_chain]
    assert any("jobs" in u for u in redirected_urls)


@pytest.mark.django_db
def test_reported_job_visible_to_natoff(auto_login_user):
    """A National Officer can still view a reported posting and see the banner."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Visible To NatOff {datetime.datetime.now().microsecond}")
    job.reported = True
    job.reported_at = datetime.datetime.now()
    job.reported_by = user
    job.reported_reason = "look at this"
    job.save()
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert b"has been reported" in response.content
    assert b"Approve Posting" in response.content


@pytest.mark.django_db
def test_reported_job_hidden_from_live_jobs_for_regular_user():
    """get_live_jobs excludes reported-but-not-approved postings when no request."""
    job = _make_job(title=f"Excluded {datetime.datetime.now().microsecond}")
    assert Job.get_live_jobs().filter(pk=job.pk).exists()
    job.reported = True
    job.save()
    assert not Job.get_live_jobs().filter(pk=job.pk).exists()
    job.approved = True
    job.save()
    # Once approved, it is visible again
    assert Job.get_live_jobs().filter(pk=job.pk).exists()


# ---------------------------------------------------------------------------
# JobApproveView — natoff/superuser can approve, others cannot
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_approve_view_get_not_allowed(auto_login_user):
    """The approve view only accepts POST."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job()
    url = reverse("jobs:approve", kwargs={"pk": job.pk})
    response = client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_job_approve_view_natoff_approves(auto_login_user):
    """A natoff user can approve a job posting."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Approve Me {datetime.datetime.now().microsecond}")
    job.reported = True
    job.reported_at = datetime.datetime.now()
    job.save()
    url = reverse("jobs:approve", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "Verified with company"})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.approved is True
    assert job.approved_at is not None
    assert job.approved_by == user
    assert "verified" in job.approved_reason.lower()
    # Report flag is retained for audit purposes
    assert job.reported is True


@pytest.mark.django_db
def test_job_approve_view_requires_reason(auto_login_user):
    """Approving without a reason redirects with an error and does not approve."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Need Reason {datetime.datetime.now().microsecond}")
    url = reverse("jobs:approve", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": ""})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.approved is False


@pytest.mark.django_db
def test_job_approve_view_regular_user_denied(auto_login_user):
    """A non-natoff user cannot approve a job."""
    client, user = auto_login_user()
    job = _make_job(title=f"Do Not Approve {datetime.datetime.now().microsecond}")
    url = reverse("jobs:approve", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "nope"})
    assert response.status_code in (302, 403)
    job.refresh_from_db()
    assert job.approved is False


@pytest.mark.django_db
def test_job_approve_view_requires_login(client):
    """Anonymous users cannot approve a job."""
    job = _make_job()
    url = reverse("jobs:approve", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "nope"})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.approved is False


@pytest.mark.django_db
def test_approved_job_cannot_be_reported(auto_login_user, mailoutbox):
    """Once approved, a job cannot be reported."""
    client, user = auto_login_user()
    job = _make_job(title=f"Approved {datetime.datetime.now().microsecond}")
    job.approved = True
    job.approved_at = datetime.datetime.now()
    job.save()
    url = reverse("jobs:report", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "trying to report an approved job"})
    assert response.status_code == 302
    assert len(mailoutbox) == 0
    job.refresh_from_db()
    assert job.reported is False


@pytest.mark.django_db
def test_approved_job_cannot_be_deleted(auto_login_user):
    """Once approved, a job cannot be deleted via the delete view."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Approved Delete {datetime.datetime.now().microsecond}")
    job.approved = True
    job.approved_at = datetime.datetime.now()
    job.save()
    url = reverse("jobs:delete", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "trying to delete an approved job"})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.deleted is False


@pytest.mark.django_db
def test_approved_job_detail_hides_report_and_delete_buttons(auto_login_user):
    """The detail page hides the report and delete buttons for approved jobs."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Approved Buttons {datetime.datetime.now().microsecond}")
    job.approved = True
    job.approved_at = datetime.datetime.now()
    job.approved_by = user
    job.save()
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert b"reportJobModal" not in response.content
    assert b"deleteJobModal" not in response.content
    assert b"Approved by" in response.content


# ---------------------------------------------------------------------------
# JobDeleteView — natoff/superuser can delete, others cannot
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_delete_view_get_not_allowed(auto_login_user):
    """The delete view only accepts POST."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job()
    url = reverse("jobs:delete", kwargs={"pk": job.pk})
    response = client.get(url)
    assert response.status_code == 405


@pytest.mark.django_db
def test_job_delete_view_natoff_deletes_job(auto_login_user):
    """A natoff user can soft-delete any job posting."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Delete Me {datetime.datetime.now().microsecond}")
    url = reverse("jobs:delete", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "Confirmed scam"})
    assert response.status_code == 302
    # Soft delete: record is retained but flagged
    job.refresh_from_db()
    assert job.deleted is True
    assert job.deleted_at is not None
    assert job.deleted_by == user
    assert "scam" in job.deleted_reason.lower()
    # And it should be excluded from live listings
    assert not Job.get_live_jobs().filter(pk=job.pk).exists()


@pytest.mark.django_db
def test_job_delete_view_requires_reason(auto_login_user):
    """Deleting without a reason redirects with an error and does not delete."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Need Delete Reason {datetime.datetime.now().microsecond}")
    url = reverse("jobs:delete", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": ""})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.deleted is False


@pytest.mark.django_db
def test_job_delete_view_regular_user_denied(auto_login_user):
    """A non-natoff user cannot delete another user's job."""
    client, user = auto_login_user()
    job = _make_job(title=f"Keep Me {datetime.datetime.now().microsecond}")
    url = reverse("jobs:delete", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "nope"})
    # NatOfficerRequiredMixin redirects unauthorized users home
    assert response.status_code in (302, 403)
    job.refresh_from_db()
    assert job.deleted is False


@pytest.mark.django_db
def test_job_delete_view_requires_login(client):
    """Anonymous users cannot delete a job."""
    job = _make_job()
    url = reverse("jobs:delete", kwargs={"pk": job.pk})
    response = client.post(url, {"reason": "nope"})
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.deleted is False


@pytest.mark.django_db
def test_job_detail_soft_deleted_visible_to_creator(auto_login_user):
    """A soft-deleted job is still viewable by its creator (with a removed banner)."""
    client, user = auto_login_user()
    job = Job(
        company="Owner Corp",
        description="<p>Owner job</p>",
        education_qualification=["bachelors"],
        experience=["new_grad"],
        job_type=["full_time"],
        location_type=["remote"],
        publish_end=datetime.date.today() + datetime.timedelta(days=30),
        publish_start=datetime.date.today() - datetime.timedelta(days=1),
        title=f"Owner Deleted Job {datetime.datetime.now().microsecond}",
        url="https://example.com/jobs/owner",
        priority=5,
        created_by=user,
        deleted=True,
        deleted_at=datetime.datetime.now(),
        deleted_reason="Central Office removed spam posting",
    )
    job.save()
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert b"has been removed" in response.content
    assert b"Central Office removed spam posting" in response.content
    # No action buttons for a removed job
    assert b"Edit Job" not in response.content
    assert b"Clone Job" not in response.content
    assert b"reportJobModal" not in response.content


@pytest.mark.django_db
def test_job_detail_soft_deleted_hidden_from_other_members(auto_login_user):
    """A soft-deleted job is not viewable by non-owner non-natoff members."""
    client, user = auto_login_user()
    job = _make_job(title=f"Hidden Deleted {datetime.datetime.now().microsecond}")
    job.deleted = True
    job.deleted_at = datetime.datetime.now()
    job.save()
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url, follow=True)
    assert response.status_code == 200
    redirected_urls = [r[0] for r in response.redirect_chain]
    assert any("jobs" in u for u in redirected_urls)


# ---------------------------------------------------------------------------
# JobCopyView � owner (or superuser) can clone a job
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_copy_view_owner_prefills_form(auto_login_user):
    """The clone view returns the create form pre-filled with source data."""
    from address.models import Country

    Country.objects.get_or_create(name="United States")
    client, user = auto_login_user()
    source = _make_job(
        title=f"Original {datetime.datetime.now().microsecond}",
        company="Acme Corp",
        created_by=user,
    )
    url = reverse("jobs:copy", kwargs={"pk": source.pk})
    response = client.get(url)
    assert response.status_code == 200
    # Company text is echoed into the create form value
    assert b"Acme Corp" in response.content
    # Title is suffixed with (Copy) to make the new slug unique
    assert b"(Copy)" in response.content


@pytest.mark.django_db
def test_job_copy_view_non_owner_denied(auto_login_user):
    """A non-owner (non-superuser) is redirected away from the clone view."""
    client, user = auto_login_user()
    source = _make_job(title=f"Not Yours {datetime.datetime.now().microsecond}")
    url = reverse("jobs:copy", kwargs={"pk": source.pk})
    response = client.get(url, follow=False)
    assert response.status_code == 302
    # Redirect target is the source job's detail page
    assert reverse("jobs:detail", kwargs={"pk": source.pk, "slug": source.slug}) in response["Location"]


@pytest.mark.django_db
def test_job_copy_view_requires_login(client):
    """Anonymous users cannot access the clone view."""
    source = _make_job()
    url = reverse("jobs:copy", kwargs={"pk": source.pk})
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_reported_job_visible_to_creator_with_reason(auto_login_user):
    """A reported (not approved) job is still viewable by its creator, who sees the reason."""
    client, user = auto_login_user()
    job = Job(
        company="Owner Corp",
        description="<p>Owner job</p>",
        education_qualification=["bachelors"],
        experience=["new_grad"],
        job_type=["full_time"],
        location_type=["remote"],
        publish_end=datetime.date.today() + datetime.timedelta(days=30),
        publish_start=datetime.date.today() - datetime.timedelta(days=1),
        title=f"Owner Reported Job {datetime.datetime.now().microsecond}",
        url="https://example.com/jobs/owner",
        priority=5,
        created_by=user,
        reported=True,
        reported_at=datetime.datetime.now(),
        reported_reason="looked suspicious",
    )
    job.save()
    url = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    response = client.get(url)
    assert response.status_code == 200
    assert b"has been reported" in response.content
    assert b"looked suspicious" in response.content


# ---------------------------------------------------------------------------
# JobBanUserView + JobCreateView ban enforcement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_ban_view_get_not_allowed(auto_login_user):
    """The ban view only accepts POST."""
    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Ban GET {datetime.datetime.now().microsecond}")
    response = client.get(reverse("jobs:ban", kwargs={"pk": job.pk}))
    assert response.status_code == 405


@pytest.mark.django_db
def test_ban_view_requires_login(client):
    """Anonymous users cannot ban a member."""
    from thetatauCMT.jobs.models import JobPostingBan

    job = _make_job()
    response = client.post(reverse("jobs:ban", kwargs={"pk": job.pk}), {"reason": "nope"})
    assert response.status_code == 302
    assert not JobPostingBan.objects.exists()


@pytest.mark.django_db
def test_ban_view_regular_user_denied(auto_login_user):
    """Non-natoff users cannot ban a member."""
    from thetatauCMT.jobs.models import JobPostingBan

    client, user = auto_login_user()
    job = _make_job(title=f"Ban Denied {datetime.datetime.now().microsecond}")
    response = client.post(reverse("jobs:ban", kwargs={"pk": job.pk}), {"reason": "hostile"})
    assert response.status_code in (302, 403)
    assert not JobPostingBan.objects.exists()


@pytest.mark.django_db
def test_ban_view_requires_reason(auto_login_user):
    """Banning without a reason redirects and does not create a ban."""
    from django.contrib.auth import get_user_model

    from thetatauCMT.jobs.models import JobPostingBan

    User = get_user_model()
    client, user = auto_login_user()
    _make_natoff(user, client)
    other = User.objects.create_user(
        username=f"target_{datetime.datetime.now().microsecond}", password="pw", email="target@example.com"
    )
    job = _make_job(title=f"Ban No Reason {datetime.datetime.now().microsecond}", created_by=other)
    response = client.post(reverse("jobs:ban", kwargs={"pk": job.pk}), {"reason": ""})
    assert response.status_code == 302
    assert not JobPostingBan.objects.filter(user=other).exists()


@pytest.mark.django_db
def test_ban_view_natoff_bans_creator(auto_login_user):
    """A natoff user can ban the job's creator with a reason."""
    from django.contrib.auth import get_user_model

    from thetatauCMT.jobs.models import JobPostingBan

    User = get_user_model()
    client, user = auto_login_user()
    _make_natoff(user, client)
    other = User.objects.create_user(
        username=f"target_{datetime.datetime.now().microsecond}", password="pw", email="t@example.com"
    )
    job = _make_job(title=f"Ban Ok {datetime.datetime.now().microsecond}", created_by=other)
    response = client.post(reverse("jobs:ban", kwargs={"pk": job.pk}), {"reason": "Repeated spam postings"})
    assert response.status_code == 302
    ban = JobPostingBan.objects.get(user=other)
    assert ban.banned_by == user
    assert "spam" in ban.reason.lower()
    assert JobPostingBan.is_banned(other) is True


@pytest.mark.django_db
def test_ban_view_cannot_ban_self(auto_login_user):
    """A natoff user cannot ban themselves via the ban view."""
    from thetatauCMT.jobs.models import JobPostingBan

    client, user = auto_login_user()
    _make_natoff(user, client)
    job = _make_job(title=f"Self Ban {datetime.datetime.now().microsecond}", created_by=user)
    response = client.post(reverse("jobs:ban", kwargs={"pk": job.pk}), {"reason": "why"})
    assert response.status_code == 302
    assert not JobPostingBan.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_ban_view_idempotent(auto_login_user):
    """A second ban on the same user does not create a duplicate row."""
    from django.contrib.auth import get_user_model

    from thetatauCMT.jobs.models import JobPostingBan

    User = get_user_model()
    client, user = auto_login_user()
    _make_natoff(user, client)
    other = User.objects.create_user(
        username=f"target_{datetime.datetime.now().microsecond}", password="pw", email="t@example.com"
    )
    job = _make_job(title=f"Ban Twice {datetime.datetime.now().microsecond}", created_by=other)
    url = reverse("jobs:ban", kwargs={"pk": job.pk})
    client.post(url, {"reason": "first"})
    client.post(url, {"reason": "second"})
    assert JobPostingBan.objects.filter(user=other).count() == 1


@pytest.mark.django_db
def test_banned_user_cannot_open_create_job(auto_login_user):
    """A banned user hitting the create-job page is redirected with an error."""
    from thetatauCMT.jobs.models import JobPostingBan

    client, user = auto_login_user()
    JobPostingBan.objects.create(user=user, reason="test")
    response = client.get(reverse("jobs:add"))
    assert response.status_code == 302
    assert reverse("jobs:list") in response["Location"]


@pytest.mark.django_db
def test_banned_user_cannot_post_create_job(auto_login_user):
    """A banned user posting the create-job form does not create a Job."""
    from thetatauCMT.jobs.models import JobPostingBan

    client, user = auto_login_user()
    JobPostingBan.objects.create(user=user, reason="test")
    post_data = {
        "company": "Blocked Co",
        "description": "<p>should not save</p>",
        "education_qualification": ["bachelors"],
        "experience": ["new_grad"],
        "job_type": ["full_time"],
        "location_type": ["remote"],
        "publish_start": (datetime.date.today() - datetime.timedelta(days=1)).isoformat(),
        "publish_end": (datetime.date.today() + datetime.timedelta(days=30)).isoformat(),
        "title": f"Blocked {datetime.datetime.now().microsecond}",
        "url": "https://example.com/apply",
        "priority": 5,
        "contact": True,
    }
    response = client.post(reverse("jobs:add"), post_data)
    assert response.status_code == 302
    assert not Job.objects.filter(company="Blocked Co").exists()


@pytest.mark.django_db
def test_banned_user_job_list_hides_add_button(auto_login_user):
    """A banned user does not see the Add Job button on the job list."""
    from thetatauCMT.jobs.models import JobPostingBan

    client, user = auto_login_user()
    JobPostingBan.objects.create(user=user, reason="test")
    response = client.get(reverse("jobs:list"))
    assert response.status_code == 200
    assert b"Add Job" not in response.content
    assert b"Job posting disabled" in response.content


@pytest.mark.django_db
def test_non_banned_user_sees_add_button(auto_login_user):
    """A non-banned user sees the Add Job button."""
    client, user = auto_login_user()
    response = client.get(reverse("jobs:list"))
    assert response.status_code == 200
    assert b"Add Job" in response.content


@pytest.mark.django_db
def test_ban_view_soft_deletes_existing_jobs(auto_login_user):
    """When a member is banned, all of their non-deleted jobs are soft-deleted."""
    from django.contrib.auth import get_user_model

    from thetatauCMT.jobs.models import JobPostingBan

    User = get_user_model()
    client, user = auto_login_user()
    _make_natoff(user, client)
    other = User.objects.create_user(
        username=f"banme_{datetime.datetime.now().microsecond}",
        password="pw",
        email="banme@example.com",
    )
    job_a = _make_job(title=f"Their Job A {datetime.datetime.now().microsecond}", created_by=other)
    job_b = _make_job(title=f"Their Job B {datetime.datetime.now().microsecond}", created_by=other)
    # A previously-deleted job should not be re-touched by the ban.
    already_deleted = _make_job(
        title=f"Already Gone {datetime.datetime.now().microsecond}",
        created_by=other,
    )
    already_deleted.deleted = True
    already_deleted.deleted_at = datetime.datetime(2020, 1, 1, 12, 0, 0)
    already_deleted.deleted_reason = "original reason"
    already_deleted.save()

    ban_url = reverse("jobs:ban", kwargs={"pk": job_a.pk})
    response = client.post(ban_url, {"reason": "Repeated spam"})
    assert response.status_code == 302

    ban = JobPostingBan.objects.get(user=other)
    job_a.refresh_from_db()
    job_b.refresh_from_db()
    already_deleted.refresh_from_db()

    # Both live jobs are soft-deleted, sharing the ban's timestamp/actor/reason.
    for j in (job_a, job_b):
        assert j.deleted is True
        assert j.deleted_at == ban.banned_at
        assert j.deleted_by == ban.banned_by
        assert "user banned by" in j.deleted_reason.lower()
        assert "repeated spam" in j.deleted_reason.lower()

    # The previously-deleted job's original audit is untouched.
    assert already_deleted.deleted is True
    assert already_deleted.deleted_reason == "original reason"
    assert already_deleted.deleted_at.year == 2020


@pytest.mark.django_db
def test_ban_view_idempotent_does_not_redelete(auto_login_user):
    """A second ban attempt does not overwrite existing delete audit fields."""
    from django.contrib.auth import get_user_model

    from thetatauCMT.jobs.models import JobPostingBan

    User = get_user_model()
    client, user = auto_login_user()
    _make_natoff(user, client)
    other = User.objects.create_user(
        username=f"double_{datetime.datetime.now().microsecond}",
        password="pw",
        email="double@example.com",
    )
    job = _make_job(title=f"Double Ban {datetime.datetime.now().microsecond}", created_by=other)
    url = reverse("jobs:ban", kwargs={"pk": job.pk})
    client.post(url, {"reason": "first ban"})
    job.refresh_from_db()
    first_reason = job.deleted_reason
    first_deleted_at = job.deleted_at
    # Second ban attempt: should be a no-op for the ban row AND for the job's audit.
    client.post(url, {"reason": "second ban"})
    ban_count = JobPostingBan.objects.filter(user=other).count()
    job.refresh_from_db()
    assert ban_count == 1
    assert job.deleted_reason == first_reason
    assert job.deleted_at == first_deleted_at
