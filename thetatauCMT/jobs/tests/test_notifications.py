"""Tests for thetatauCMT/jobs/notifications.py and related integrations.

Covers:
  * Auto-approval + JobCreatedNotification on job creation.
  * Central Office notifications on delete and ban.
  * Immediate JobSearch match notifications.
  * The ``job_search_notify`` management command (daily / weekly digests).
"""

import datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from thetatauCMT.configs.models import Config
from thetatauCMT.jobs.models import Job, JobPostingBan, JobSearch, Keyword
from thetatauCMT.jobs.notifications import (
    JobCreatedNotification,
    JobDeletedNotification,
    _get_jobs_creation_emails,
    digest_since,
    notify_matching_searches,
)
from thetatauCMT.jobs.tests.test_models import _make_job


def _set_jobs_creation_email(value="jobs-notify@example.com"):
    Config.objects.create(
        key="JOBS_CREATION_EMAIL",
        value=f"<p>{value}</p>",
        description="Test recipient(s) for new job postings.",
    )


def _make_natoff(user, client=None):
    group, _ = Group.objects.get_or_create(name="natoff")
    user.groups.add(group)
    if client is not None:
        client.force_login(user)


# ---------------------------------------------------------------------------
# _get_jobs_creation_emails — reads Config, strips HTML, splits list
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_jobs_creation_emails_empty_when_no_config():
    assert _get_jobs_creation_emails() == []


@pytest.mark.django_db
def test_get_jobs_creation_emails_strips_html():
    _set_jobs_creation_email("alerts@example.com")
    assert _get_jobs_creation_emails() == ["alerts@example.com"]


@pytest.mark.django_db
def test_get_jobs_creation_emails_splits_multiple():
    Config.objects.create(
        key="JOBS_CREATION_EMAIL",
        value="<p>one@example.com, two@example.com; three@example.com</p>",
        description="",
    )
    result = _get_jobs_creation_emails()
    assert result == ["one@example.com", "two@example.com", "three@example.com"]


@pytest.mark.django_db
def test_get_jobs_creation_emails_dedups_case_insensitive():
    Config.objects.create(
        key="JOBS_CREATION_EMAIL",
        value="<p>Same@Example.com, same@example.com</p>",
        description="",
    )
    assert _get_jobs_creation_emails() == ["Same@Example.com"]


# ---------------------------------------------------------------------------
# JobCreatedNotification defaults
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_created_notification_uses_config_recipients():
    _set_jobs_creation_email("primary@example.com")
    job = _make_job(title=f"Notif Job {datetime.datetime.now().microsecond}")
    notif = JobCreatedNotification(job)
    assert notif.to_emails == ["primary@example.com"]
    assert notif.subject.startswith("[CMT] New Job Posting")
    assert notif.context["job"].pk == job.pk


@pytest.mark.django_db
def test_job_created_notification_no_recipients_when_config_missing():
    job = _make_job(title=f"No Recipient Job {datetime.datetime.now().microsecond}")
    notif = JobCreatedNotification(job)
    assert notif.to_emails == []


@pytest.mark.django_db
def test_job_created_notification_includes_creator_line_when_contact_true():
    """When ``job.contact`` is True the creator name/email is shared."""
    User = get_user_model()
    poster = User.objects.create_user(
        username=f"poster_{datetime.datetime.now().microsecond}",
        password="pw",
        email="poster@example.com",
    )
    job = _make_job(
        title=f"Contact Yes {datetime.datetime.now().microsecond}",
        contact=True,
        created_by=poster,
    )
    notif = JobCreatedNotification(job)
    assert "poster@example.com" in notif.context["creator_line"]


@pytest.mark.django_db
def test_job_created_notification_hides_creator_line_when_contact_false():
    """When ``job.contact`` is False the poster opted out; hide creator info."""
    User = get_user_model()
    poster = User.objects.create_user(
        username=f"poster_{datetime.datetime.now().microsecond}",
        password="pw",
        email="poster@example.com",
    )
    job = _make_job(
        title=f"Contact No {datetime.datetime.now().microsecond}",
        contact=False,
        created_by=poster,
    )
    notif = JobCreatedNotification(job)
    assert notif.context["creator_line"] == ""
    assert notif.context["creator_chapter"] == ""


# ---------------------------------------------------------------------------
# JobCreateView — sends JobCreatedNotification via config recipient
# ---------------------------------------------------------------------------


def _job_post_data(**overrides):
    """Build a POST body that :class:`JobForm` accepts.

    Requires seeded ``Locality`` rows (present in the shared test DB from
    ``zip_code_database.csv``); if none exist we create a minimal one so
    the ``location`` M2M field can be resolved.
    """
    from address.models import Country, Locality, State

    country, _ = Country.objects.get_or_create(name="United States")
    locality = Locality.objects.order_by("pk").first()
    if locality is None:
        state, _ = State.objects.get_or_create(name="Test", country=country)
        locality = Locality.objects.create(name="Testville", postal_code="12345", state=state)
    data = {
        "company": "Test Co",
        "description": "<p>Test description body</p>",
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
        "majors_specific": False,
        "location": [str(locality.pk)],
        "country": str(country.pk),
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_job_create_view_sends_creation_email(auto_login_user, mailoutbox):
    _set_jobs_creation_email("alerts@example.com")
    client, user = auto_login_user()
    url = reverse("jobs:add")
    response = client.post(url, _job_post_data())
    assert response.status_code == 302
    creation_emails = [m for m in mailoutbox if m.subject.startswith("[CMT] New Job Posting")]
    assert len(creation_emails) == 1
    assert "alerts@example.com" in creation_emails[0].to


@pytest.mark.django_db
def test_job_create_view_no_creation_email_when_config_missing(auto_login_user, mailoutbox):
    client, user = auto_login_user()
    url = reverse("jobs:add")
    response = client.post(url, _job_post_data())
    assert response.status_code == 302
    creation_emails = [m for m in mailoutbox if m.subject.startswith("[CMT] New Job Posting")]
    assert creation_emails == []


@pytest.mark.django_db
def test_job_create_view_natoff_auto_approves(auto_login_user, mailoutbox):
    _set_jobs_creation_email("alerts@example.com")
    client, user = auto_login_user()
    _make_natoff(user, client=client)
    url = reverse("jobs:add")
    response = client.post(url, _job_post_data(title=f"Auto-Approved {datetime.datetime.now().microsecond}"))
    assert response.status_code == 302
    job = Job.objects.filter(created_by=user).order_by("-created").first()
    assert job is not None
    assert job.approved is True
    assert job.approved_by == user
    assert job.approved_at is not None
    assert "auto-approved" in (job.approved_reason or "").lower()


@pytest.mark.django_db
def test_job_create_view_regular_user_does_not_auto_approve(auto_login_user):
    _set_jobs_creation_email("alerts@example.com")
    client, user = auto_login_user()
    url = reverse("jobs:add")
    response = client.post(url, _job_post_data(title=f"Regular {datetime.datetime.now().microsecond}"))
    assert response.status_code == 302
    job = Job.objects.filter(created_by=user).order_by("-created").first()
    assert job is not None
    assert job.approved is False


@pytest.mark.django_db
def test_job_create_form_shows_auto_approval_note_for_natoff(auto_login_user):
    client, user = auto_login_user()
    _make_natoff(user, client=client)
    from address.models import Country

    Country.objects.get_or_create(name="United States")
    response = client.get(reverse("jobs:add"))
    assert response.status_code == 200
    assert b"automatically approved" in response.content


@pytest.mark.django_db
def test_job_create_form_hides_auto_approval_note_for_regular_user(auto_login_user):
    client, user = auto_login_user()
    from address.models import Country

    Country.objects.get_or_create(name="United States")
    response = client.get(reverse("jobs:add"))
    assert response.status_code == 200
    assert b"automatically approved" not in response.content


# ---------------------------------------------------------------------------
# JobDeleteView — Central Office notification
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_delete_view_notifies_central_office(auto_login_user, mailoutbox):
    client, user = auto_login_user()
    _make_natoff(user, client=client)
    job = _make_job(title=f"Delete Notify {datetime.datetime.now().microsecond}")
    response = client.post(
        reverse("jobs:delete", kwargs={"pk": job.pk}),
        {"reason": "Confirmed spam"},
    )
    assert response.status_code == 302
    delete_mails = [m for m in mailoutbox if m.subject.startswith("[CMT] Job Posting Removed")]
    assert len(delete_mails) == 1
    email = delete_mails[0]
    assert "central.office@thetatau.org" in email.to
    assert job.title in email.subject


@pytest.mark.django_db
def test_job_delete_view_second_delete_does_not_reemail(auto_login_user, mailoutbox):
    client, user = auto_login_user()
    _make_natoff(user, client=client)
    job = _make_job(title=f"Delete Twice {datetime.datetime.now().microsecond}")
    job.deleted = True
    job.deleted_at = timezone.now()
    job.deleted_by = user
    job.deleted_reason = "prior removal"
    job.save()
    response = client.post(
        reverse("jobs:delete", kwargs={"pk": job.pk}),
        {"reason": "second attempt"},
    )
    assert response.status_code == 302
    delete_mails = [m for m in mailoutbox if m.subject.startswith("[CMT] Job Posting Removed")]
    assert delete_mails == []


# ---------------------------------------------------------------------------
# JobBanUserView — Central Office notification
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_ban_view_notifies_central_office(auto_login_user, mailoutbox):
    User = get_user_model()
    client, user = auto_login_user()
    _make_natoff(user, client=client)
    other = User.objects.create_user(
        username=f"target_{datetime.datetime.now().microsecond}",
        password="pw",
        email="target@example.com",
    )
    job = _make_job(title=f"Ban Notify {datetime.datetime.now().microsecond}", created_by=other)
    response = client.post(
        reverse("jobs:ban", kwargs={"pk": job.pk}),
        {"reason": "Repeated spam"},
    )
    assert response.status_code == 302
    ban_mails = [m for m in mailoutbox if m.subject.startswith("[CMT] Member Barred")]
    assert len(ban_mails) == 1
    email = ban_mails[0]
    assert "central.office@thetatau.org" in email.to
    body = " ".join(str(p) for p in [email.body] + list(getattr(email, "alternatives", [])))
    assert "target@example.com" in body


@pytest.mark.django_db
def test_job_ban_view_idempotent_does_not_reemail(auto_login_user, mailoutbox):
    User = get_user_model()
    client, user = auto_login_user()
    _make_natoff(user, client=client)
    other = User.objects.create_user(
        username=f"target_{datetime.datetime.now().microsecond}",
        password="pw",
        email="target@example.com",
    )
    JobPostingBan.objects.create(user=other, banned_by=user, reason="already banned")
    job = _make_job(title=f"Ban Again {datetime.datetime.now().microsecond}", created_by=other)
    mailoutbox.clear()
    response = client.post(
        reverse("jobs:ban", kwargs={"pk": job.pk}),
        {"reason": "second attempt"},
    )
    assert response.status_code == 302
    ban_mails = [m for m in mailoutbox if m.subject.startswith("[CMT] Member Barred")]
    assert ban_mails == []


# ---------------------------------------------------------------------------
# Immediate JobSearch match notifications on job creation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_creation_triggers_immediate_search_notification(auto_login_user, mailoutbox):
    _set_jobs_creation_email("alerts@example.com")
    User = get_user_model()
    client, user = auto_login_user()
    watcher = User.objects.create_user(
        username=f"watcher_{datetime.datetime.now().microsecond}",
        password="pw",
        email="watcher@example.com",
    )
    JobSearch.objects.create(
        search_title="Python roles",
        search_description="Any Python job",
        title="Python",
        title_filter=JobSearch.FILTER.include.name,
        notification=JobSearch.NOTIFICATION.immediate.name,
        created_by=watcher,
    )
    url = reverse("jobs:add")
    response = client.post(
        url,
        _job_post_data(title=f"Senior Python Engineer {datetime.datetime.now().microsecond}"),
    )
    assert response.status_code == 302
    match_mails = [m for m in mailoutbox if "watcher@example.com" in m.to]
    assert len(match_mails) == 1
    assert "Python" in match_mails[0].subject


@pytest.mark.django_db
def test_job_creation_does_not_notify_daily_search(auto_login_user, mailoutbox):
    _set_jobs_creation_email("alerts@example.com")
    User = get_user_model()
    client, user = auto_login_user()
    watcher = User.objects.create_user(
        username=f"watcher_{datetime.datetime.now().microsecond}",
        password="pw",
        email="watcher@example.com",
    )
    JobSearch.objects.create(
        search_title="Python roles",
        search_description="Any Python job",
        title="Python",
        title_filter=JobSearch.FILTER.include.name,
        notification=JobSearch.NOTIFICATION.daily.name,
        created_by=watcher,
    )
    url = reverse("jobs:add")
    response = client.post(
        url,
        _job_post_data(title=f"Senior Python Engineer {datetime.datetime.now().microsecond}"),
    )
    assert response.status_code == 302
    match_mails = [m for m in mailoutbox if "watcher@example.com" in m.to]
    assert match_mails == []


@pytest.mark.django_db
def test_job_creation_does_not_notify_non_matching_search(auto_login_user, mailoutbox):
    _set_jobs_creation_email("alerts@example.com")
    User = get_user_model()
    client, user = auto_login_user()
    watcher = User.objects.create_user(
        username=f"watcher_{datetime.datetime.now().microsecond}",
        password="pw",
        email="watcher@example.com",
    )
    JobSearch.objects.create(
        search_title="Rust roles",
        search_description="Rust only",
        title="Rust",
        title_filter=JobSearch.FILTER.include.name,
        notification=JobSearch.NOTIFICATION.immediate.name,
        created_by=watcher,
    )
    url = reverse("jobs:add")
    response = client.post(
        url,
        _job_post_data(title=f"Python Engineer {datetime.datetime.now().microsecond}"),
    )
    assert response.status_code == 302
    match_mails = [m for m in mailoutbox if "watcher@example.com" in m.to]
    assert match_mails == []


@pytest.mark.django_db
def test_empty_search_is_skipped_by_notify_matching_searches(mailoutbox):
    """A search with no active filters would match every job; skip it."""
    User = get_user_model()
    watcher = User.objects.create_user(
        username=f"empty_{datetime.datetime.now().microsecond}",
        password="pw",
        email="empty@example.com",
    )
    JobSearch.objects.create(
        search_title="Everything",
        search_description="No filters",
        notification=JobSearch.NOTIFICATION.immediate.name,
        created_by=watcher,
    )
    job = _make_job(title=f"Anything {datetime.datetime.now().microsecond}")
    sent = notify_matching_searches(Job.objects.filter(pk=job.pk), JobSearch.NOTIFICATION.immediate.name)
    assert sent == 0
    assert [m for m in mailoutbox if "empty@example.com" in m.to] == []


# ---------------------------------------------------------------------------
# JobDeletedNotification defaults
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_deleted_notification_populates_context():
    User = get_user_model()
    actor = User.objects.create_user(
        username=f"actor_{datetime.datetime.now().microsecond}",
        password="pw",
        email="actor@example.com",
    )
    job = _make_job(title=f"Delete Direct {datetime.datetime.now().microsecond}")
    job.deleted = True
    job.deleted_at = timezone.now()
    job.deleted_by = actor
    job.deleted_reason = "spam"
    job.save()
    notif = JobDeletedNotification(job)
    assert notif.to_emails == ["central.office@thetatau.org"]
    assert "actor@example.com" in notif.context["actor_line"]
    assert notif.context["job"].pk == job.pk


# ---------------------------------------------------------------------------
# digest_since helper
# ---------------------------------------------------------------------------


def test_digest_since_daily():
    now = timezone.now()
    since = digest_since(JobSearch.NOTIFICATION.daily.name, now=now)
    assert (now - since) == timezone.timedelta(days=1)


def test_digest_since_weekly():
    now = timezone.now()
    since = digest_since(JobSearch.NOTIFICATION.weekly.name, now=now)
    assert (now - since) == timezone.timedelta(days=7)


def test_digest_since_rejects_unknown():
    with pytest.raises(ValueError):
        digest_since("something-else")


# ---------------------------------------------------------------------------
# job_search_notify management command
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_job_search_notify_daily_sends_matches(mailoutbox):
    User = get_user_model()
    watcher = User.objects.create_user(
        username=f"daily_{datetime.datetime.now().microsecond}",
        password="pw",
        email="daily@example.com",
    )
    JobSearch.objects.create(
        search_title="Any job",
        search_description="Company match",
        company="Acme",
        company_filter=JobSearch.FILTER.include.name,
        notification=JobSearch.NOTIFICATION.daily.name,
        created_by=watcher,
    )
    _make_job(title=f"Recent Match {datetime.datetime.now().microsecond}", company="Acme Corp")
    call_command("job_search_notify", "--frequency", "daily")
    match_mails = [m for m in mailoutbox if "daily@example.com" in m.to]
    assert len(match_mails) == 1


@pytest.mark.django_db
def test_job_search_notify_weekly_ignores_daily_search(mailoutbox):
    User = get_user_model()
    watcher = User.objects.create_user(
        username=f"weekly_{datetime.datetime.now().microsecond}",
        password="pw",
        email="weekly@example.com",
    )
    # Search wants daily notifications, but we only run --frequency weekly
    JobSearch.objects.create(
        search_title="Any job",
        search_description="Company match",
        company="Acme",
        company_filter=JobSearch.FILTER.include.name,
        notification=JobSearch.NOTIFICATION.daily.name,
        created_by=watcher,
    )
    _make_job(title=f"Recent Match {datetime.datetime.now().microsecond}", company="Acme Corp")
    call_command("job_search_notify", "--frequency", "weekly")
    match_mails = [m for m in mailoutbox if "weekly@example.com" in m.to]
    assert match_mails == []


@pytest.mark.django_db
def test_job_search_notify_default_runs_both(mailoutbox):
    User = get_user_model()
    daily_user = User.objects.create_user(
        username=f"d_{datetime.datetime.now().microsecond}",
        password="pw",
        email="d@example.com",
    )
    weekly_user = User.objects.create_user(
        username=f"w_{datetime.datetime.now().microsecond}",
        password="pw",
        email="w@example.com",
    )
    JobSearch.objects.create(
        search_title="Daily",
        search_description="",
        company="Acme",
        company_filter=JobSearch.FILTER.include.name,
        notification=JobSearch.NOTIFICATION.daily.name,
        created_by=daily_user,
    )
    JobSearch.objects.create(
        search_title="Weekly",
        search_description="",
        company="Acme",
        company_filter=JobSearch.FILTER.include.name,
        notification=JobSearch.NOTIFICATION.weekly.name,
        created_by=weekly_user,
    )
    _make_job(title=f"Both Match {datetime.datetime.now().microsecond}", company="Acme Corp")
    call_command("job_search_notify")
    daily_mails = [m for m in mailoutbox if "d@example.com" in m.to]
    weekly_mails = [m for m in mailoutbox if "w@example.com" in m.to]
    assert len(daily_mails) == 1
    assert len(weekly_mails) == 1


@pytest.mark.django_db
def test_job_search_notify_excludes_deleted_jobs(mailoutbox):
    User = get_user_model()
    watcher = User.objects.create_user(
        username=f"del_{datetime.datetime.now().microsecond}",
        password="pw",
        email="del@example.com",
    )
    JobSearch.objects.create(
        search_title="Any",
        search_description="",
        company="Acme",
        company_filter=JobSearch.FILTER.include.name,
        notification=JobSearch.NOTIFICATION.daily.name,
        created_by=watcher,
    )
    job = _make_job(title=f"Soft Deleted {datetime.datetime.now().microsecond}", company="Acme Corp")
    job.deleted = True
    job.deleted_at = timezone.now()
    job.save()
    call_command("job_search_notify", "--frequency", "daily")
    match_mails = [m for m in mailoutbox if "del@example.com" in m.to]
    assert match_mails == []


@pytest.mark.django_db
def test_job_search_notify_matches_keywords(mailoutbox):
    """M2M keyword filter is honoured by JobSearch.search() and the command."""
    User = get_user_model()
    kw = Keyword.objects.create(name="python")
    watcher = User.objects.create_user(
        username=f"kw_{datetime.datetime.now().microsecond}",
        password="pw",
        email="kw@example.com",
    )
    search = JobSearch.objects.create(
        search_title="Python via keyword",
        search_description="",
        notification=JobSearch.NOTIFICATION.daily.name,
        keywords_filter=JobSearch.FILTER.include.name,
        created_by=watcher,
    )
    search.keywords.add(kw)
    job = _make_job(title=f"Kw Match {datetime.datetime.now().microsecond}")
    job.keywords.add(kw)
    call_command("job_search_notify", "--frequency", "daily")
    match_mails = [m for m in mailoutbox if "kw@example.com" in m.to]
    assert len(match_mails) == 1
