"""Email notifications for the jobs app.

All ``EmailNotification`` classes here are registered with django-herald so
they show up in the herald admin/preview UI, and are constructed with a
single object (``Job`` / ``JobPostingBan`` / ``JobSearch``) plus the
minimum extra context the template needs.

Two module-level helpers wrap the notifications for use from views and
management commands:

* :func:`notify_job_created` – fires ``JobCreatedNotification`` to the
  address(es) stored in the ``JOBS_CREATION_EMAIL`` :class:`Config` row and
  triggers any ``JobSearch`` records whose ``notification == 'immediate'``.
* :func:`notify_matching_searches` – used by
  ``manage.py job_search_notify`` to email the ``daily`` / ``weekly``
  digests for a given window of jobs.
"""

import logging
import re

from django.conf import settings
from django.utils import timezone
from django.utils.html import strip_tags
from herald import registry
from herald.base import EmailNotification

from thetatauCMT.configs.models import Config

from .models import Job, JobSearch

logger = logging.getLogger(__name__)

# Address(es) the JobCreatedNotification is sent to. Users can enter one
# address or a list separated by comma / semicolon / whitespace inside the
# CKEditor Config row and we split it out here.
_EMAIL_SPLIT_RE = re.compile(r"[\s,;]+")
_JOBS_CREATION_EMAIL_KEY = "JOBS_CREATION_EMAIL"

CENTRAL_OFFICE_EMAIL = "central.office@thetatau.org"
CMT_CC_EMAIL = "cmt@thetatau.org"

_FREQUENCY_LABELS = {
    JobSearch.NOTIFICATION.immediate.name: "Immediate",
    JobSearch.NOTIFICATION.daily.name: "Daily",
    JobSearch.NOTIFICATION.weekly.name: "Weekly",
}


def _get_jobs_creation_emails():
    """Return the recipient list for :class:`JobCreatedNotification`.

    Reads the ``JOBS_CREATION_EMAIL`` :class:`Config` row (CKEditor value),
    strips HTML, and splits on whitespace / comma / semicolon so a single
    row can hold multiple addresses.
    """
    raw = Config.get_value(_JOBS_CREATION_EMAIL_KEY, clean=True) or ""
    raw = strip_tags(raw).strip()
    if not raw:
        return []
    parts = [p.strip() for p in _EMAIL_SPLIT_RE.split(raw) if p.strip()]
    # De-dup while preserving order
    seen = set()
    emails = []
    for part in parts:
        low = part.lower()
        if low in seen:
            continue
        seen.add(low)
        emails.append(part)
    return emails


def _job_detail_url(job):
    """Absolute URL to the given job's detail page."""
    from django.urls import NoReverseMatch, reverse

    host = (getattr(settings, "CURRENT_URL", "") or "").rstrip("/")
    try:
        path = reverse("jobs:detail", kwargs={"pk": job.pk, "slug": job.slug})
    except NoReverseMatch:
        path = f"/jobs/{job.pk}/{job.slug}/"
    return f"{host}{path}"


def _job_search_url(job_search):
    from django.urls import NoReverseMatch, reverse

    host = (getattr(settings, "CURRENT_URL", "") or "").rstrip("/")
    try:
        path = reverse("jobs:search_filter", kwargs={"pk": job_search.pk})
    except NoReverseMatch:
        path = f"/jobs/search/{job_search.pk}/"
    return f"{host}{path}"


def _search_matches(job_search, job_qs):
    """Return the subset of ``job_qs`` that satisfies ``job_search``.

    Also returns ``True`` in the second position when the search has at
    least one active filter (any of ANDs/ORs/NOTs); a search with no
    active filters would match every live job so we skip it to avoid
    accidentally spamming every posting to the search owner.
    """
    matched_qs, ands, ors, nots = job_search.search(job_qs)
    has_active_filter = bool(ands or ors or nots)
    return matched_qs, has_active_filter


# --------------------------------------------------------------------------- #
#  Notifications
# --------------------------------------------------------------------------- #


@registry.register_decorator()
class JobCreatedNotification(EmailNotification):
    """Sent to the ``JOBS_CREATION_EMAIL`` recipients whenever a job is posted."""

    render_types = ["html"]
    template_name = "job_created"
    subject = "[CMT] New Job Posting"

    def __init__(self, job, recipients=None):
        if recipients is None:
            recipients = _get_jobs_creation_emails()
        self.to_emails = list(recipients)
        self.cc = []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        self.subject = f"[CMT] New Job Posting: {job.title}"
        creator = job.created_by
        creator_line = ""
        creator_chapter = ""
        # Respect the poster's contact preference: when ``job.contact`` is
        # False the poster opted out of having their name/email surfaced on
        # the listing, so we also omit it from the creation notification.
        if creator is not None and job.contact:
            creator_line = f"{creator.get_full_name() or creator.get_username()} ({creator.email})"
            chapter = getattr(creator, "current_chapter", None)
            creator_chapter = str(chapter) if chapter else ""
        self.context = {
            "job": job,
            "creator_line": creator_line,
            "creator_chapter": creator_chapter,
            "job_detail_url": _job_detail_url(job),
            "auto_approved": bool(job.approved),
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        return [Job.objects.order_by("-created").first()]


@registry.register_decorator()
class JobDeletedNotification(EmailNotification):
    """Sent to the Central Office when a National Officer soft-deletes a job."""

    render_types = ["html"]
    template_name = "job_deleted"
    subject = "[CMT] Job Posting Removed"

    def __init__(self, job):
        self.to_emails = [CENTRAL_OFFICE_EMAIL]
        self.cc = [CMT_CC_EMAIL]
        self.reply_to = [CMT_CC_EMAIL]
        self.subject = f"[CMT] Job Posting Removed: {job.title}"
        actor = job.deleted_by
        actor_line = (
            f"{actor.get_full_name() or actor.get_username()} ({actor.email})" if actor is not None else "(unknown)"
        )
        creator = job.created_by
        creator_line = (
            f"{creator.get_full_name() or creator.get_username()} ({creator.email})"
            if creator is not None
            else "(unknown)"
        )
        self.context = {
            "job": job,
            "actor_line": actor_line,
            "creator_line": creator_line,
            "job_detail_url": _job_detail_url(job),
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        return [Job.objects.filter(deleted=True).order_by("-deleted_at").first() or Job.objects.first()]


@registry.register_decorator()
class JobBannedNotification(EmailNotification):
    """Sent to the Central Office when a National Officer bans a member."""

    render_types = ["html"]
    template_name = "job_banned"
    subject = "[CMT] Member Barred from Job Postings"

    def __init__(self, ban, affected_count=0):
        self.to_emails = [CENTRAL_OFFICE_EMAIL]
        self.cc = [CMT_CC_EMAIL]
        self.reply_to = [CMT_CC_EMAIL]
        target = ban.user
        target_label = target.get_full_name() or target.get_username() if target is not None else "(unknown)"
        self.subject = f"[CMT] Member Barred from Job Postings: {target_label}"
        actor = ban.banned_by
        actor_line = (
            f"{actor.get_full_name() or actor.get_username()} ({actor.email})" if actor is not None else "(unknown)"
        )
        target_line = f"{target_label} ({target.email})" if target is not None else "(unknown)"
        target_chapter = ""
        if target is not None:
            chapter = getattr(target, "current_chapter", None)
            target_chapter = str(chapter) if chapter else ""
        self.context = {
            "ban": ban,
            "target_line": target_line,
            "target_chapter": target_chapter,
            "actor_line": actor_line,
            "affected_count": affected_count,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        from .models import JobPostingBan

        ban = JobPostingBan.objects.order_by("-banned_at").first()
        return [ban, 0] if ban is not None else [None, 0]


@registry.register_decorator()
class JobSearchMatchNotification(EmailNotification):
    """Sent to a ``JobSearch`` owner when new jobs match their saved search."""

    render_types = ["html"]
    template_name = "job_search_match"
    subject = "[CMT] New Jobs Matching Your Search"

    def __init__(self, job_search, jobs, frequency=None):
        user = job_search.created_by
        primary = getattr(user, "email", "") if user is not None else ""
        emails = {primary} if primary else set()
        if user is not None:
            emails |= set(user.emailaddress_set.values_list("email", flat=True))
            email_school = getattr(user, "email_school", "") or ""
            if email_school:
                emails.add(email_school)
        self.to_emails = [e for e in emails if e]
        self.cc = []
        self.reply_to = [CENTRAL_OFFICE_EMAIL]
        if frequency is None:
            frequency = job_search.notification
        frequency_label = _FREQUENCY_LABELS.get(frequency, "New")
        jobs_list = list(jobs)
        if len(jobs_list) == 1:
            self.subject = f"[CMT] {frequency_label} Match: {jobs_list[0].title} ({job_search.search_title})"
        else:
            self.subject = (
                f"[CMT] {frequency_label} Job Matches for {job_search.search_title}" f" ({len(jobs_list)} new)"
            )
        job_rows = [{"job": job, "url": _job_detail_url(job)} for job in jobs_list]
        self.context = {
            "user": user,
            "job_search": job_search,
            "job_search_url": _job_search_url(job_search),
            "job_rows": job_rows,
            "job_count": len(jobs_list),
            "frequency_label": frequency_label,
            "host": settings.CURRENT_URL,
        }

    @staticmethod
    def get_demo_args():
        search = JobSearch.objects.order_by("-modified").first()
        if search is None:
            return [None, [], JobSearch.NOTIFICATION.immediate.name]
        recent = Job.get_live_jobs().order_by("-created")[:3]
        return [search, list(recent), JobSearch.NOTIFICATION.immediate.name]


# --------------------------------------------------------------------------- #
#  High-level helpers
# --------------------------------------------------------------------------- #


def notify_job_created(job):
    """Fire creation + immediate-match notifications for a freshly saved job.

    Errors are logged but not re-raised so that a mail-server failure does
    not abort job creation.
    """
    try:
        recipients = _get_jobs_creation_emails()
        if recipients:
            JobCreatedNotification(job, recipients=recipients).send()
        else:
            logger.info("JOBS_CREATION_EMAIL config is empty; skipping JobCreatedNotification.")
    except Exception:
        logger.exception("Failed to send JobCreatedNotification for job pk=%s", job.pk)
    try:
        notify_matching_searches(
            Job.objects.filter(pk=job.pk),
            JobSearch.NOTIFICATION.immediate.name,
        )
    except Exception:
        logger.exception("Failed to send immediate JobSearch notifications for job pk=%s", job.pk)


def notify_job_deleted(job):
    try:
        JobDeletedNotification(job).send()
    except Exception:
        logger.exception("Failed to send JobDeletedNotification for job pk=%s", job.pk)


def notify_job_banned(ban, affected_count=0):
    try:
        JobBannedNotification(ban, affected_count=affected_count).send()
    except Exception:
        logger.exception("Failed to send JobBannedNotification for ban pk=%s", ban.pk)


def notify_matching_searches(job_qs, frequency):
    """Send :class:`JobSearchMatchNotification` for every matching search.

    Iterates ``JobSearch`` rows whose ``notification`` equals ``frequency``,
    keeps only those with at least one active filter, and sends one email
    per (owner, search) pair listing the matched subset of ``job_qs``.

    Returns the number of emails actually sent (useful for management
    command output).
    """
    sent = 0
    searches = JobSearch.objects.filter(notification=frequency).select_related("created_by")
    for search in searches:
        owner = search.created_by
        if owner is None or not getattr(owner, "email", ""):
            continue
        matched_qs, has_active_filter = _search_matches(search, job_qs)
        if not has_active_filter:
            continue
        matches = list(matched_qs)
        if not matches:
            continue
        try:
            JobSearchMatchNotification(search, matches, frequency=frequency).send()
            sent += 1
        except Exception:
            logger.exception(
                "Failed to send JobSearchMatchNotification for search pk=%s user=%s",
                search.pk,
                getattr(owner, "pk", None),
            )
    return sent


def digest_since(frequency, now=None):
    """Return the ``created__gte`` cutoff for a digest of the given frequency.

    ``daily`` → 24 hours before now, ``weekly`` → 7 days before now.
    """
    now = now or timezone.now()
    if frequency == JobSearch.NOTIFICATION.daily.name:
        return now - timezone.timedelta(days=1)
    if frequency == JobSearch.NOTIFICATION.weekly.name:
        return now - timezone.timedelta(days=7)
    raise ValueError(f"Unsupported digest frequency: {frequency}")
