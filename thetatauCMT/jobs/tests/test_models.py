import datetime
import pytest
from django.utils import timezone
from django.utils.text import slugify
from thetatauCMT.jobs.models import Job, Keyword, Major, JobSearch


def _make_job(**kwargs):
    defaults = dict(
        company="Acme Corp",
        description="<p>Great job opportunity</p>",
        education_qualification=["bachelors"],
        experience=["new_grad"],
        job_type=["full_time"],
        location_type=["remote"],
        publish_end=datetime.date.today() + datetime.timedelta(days=30),
        publish_start=datetime.date.today() - datetime.timedelta(days=1),
        title=f"Software Engineer {datetime.datetime.now().microsecond}",
        url="https://example.com/jobs/1",
        priority=5,
    )
    defaults.update(kwargs)
    job = Job(**defaults)
    job.save()
    return job


# ---------------------------------------------------------------------------
# Keyword and Major __str__
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_keyword_str():
    kw = Keyword.objects.create(name="Python")
    assert str(kw) == "Python"


@pytest.mark.django_db
def test_major_str():
    major = Major.objects.create(name="Computer Science")
    assert str(major) == "Computer Science"


# ---------------------------------------------------------------------------
# Job.save — slug generation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_job_save_sets_slug_from_title():
    job = _make_job(title="Senior Python Developer")
    assert job.slug == slugify("Senior Python Developer")


@pytest.mark.django_db
def test_job_save_slug_unique_when_duplicate_title():
    """Two jobs with the same title get distinct slugs."""
    unique = f"same-title-{datetime.datetime.now().microsecond}"
    job1 = _make_job(title=unique)
    job2 = _make_job(title=unique)
    assert job1.slug != job2.slug


@pytest.mark.django_db
def test_job_save_does_not_change_slug_on_update():
    job = _make_job(title="Stable Slug Job")
    original_slug = job.slug
    job.company = "Updated Corp"
    job.save()
    job.refresh_from_db()
    assert job.slug == original_slug


# ---------------------------------------------------------------------------
# Job.get_live_jobs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_get_live_jobs_includes_active_job():
    job = _make_job(
        publish_start=datetime.date.today() - datetime.timedelta(days=1),
        publish_end=datetime.date.today() + datetime.timedelta(days=10),
        title=f"Active Job {datetime.datetime.now().microsecond}",
    )
    live = Job.get_live_jobs()
    assert live.filter(pk=job.pk).exists()


@pytest.mark.django_db
def test_get_live_jobs_excludes_expired_job():
    job = _make_job(
        publish_start=datetime.date.today() - datetime.timedelta(days=60),
        publish_end=datetime.date.today() - datetime.timedelta(days=1),
        title=f"Expired Job {datetime.datetime.now().microsecond}",
    )
    live = Job.get_live_jobs()
    assert not live.filter(pk=job.pk).exists()


@pytest.mark.django_db
def test_get_live_jobs_excludes_future_job():
    job = _make_job(
        publish_start=datetime.date.today() + datetime.timedelta(days=5),
        publish_end=datetime.date.today() + datetime.timedelta(days=30),
        title=f"Future Job {datetime.datetime.now().microsecond}",
    )
    live = Job.get_live_jobs()
    assert not live.filter(pk=job.pk).exists()


# ---------------------------------------------------------------------------
# Job JOB_TYPE enum helper
# ---------------------------------------------------------------------------

def test_job_type_get_value():
    assert Job.JOB_TYPE.get_value("intern") == "Internship"
    assert Job.JOB_TYPE.get_value("full_time") == "Full Time"


def test_experience_get_value():
    assert Job.EXPERIENCE.get_value("new_grad") == "New Grad"
    assert Job.EXPERIENCE.get_value("twenty_plus") == "20+ years"
