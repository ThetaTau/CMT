"""The daily and monthly Chapter Support Specialist digests (CSSWI-6; Q14, Q25 C, S17).

``send_css_digests`` runs both. The daily digest carries the emails that reach a CSS only
through the digest, in full, and lists the time-sensitive ones they already got on CC.
The monthly digest covers each of their chapters: last month's emails in one line each,
and what is still open now.
"""

import datetime
from itertools import groupby
from operator import attrgetter

from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from herald.models import SentNotification

from core.models import previous_month_period

from .models import SupportDigestEntry
from .services import css_chapters, current_css_users

OFFICER_TITLES = ["Regent", "Scribe", "Vice Regent", "Treasurer", "Corresponding Secretary"]


def chapter_url(chapter):
    return f"{settings.CURRENT_URL}{reverse('chapters:detail', kwargs={'slug': chapter.slug})}"


def send_daily_digests(now=None, dry_run=False):
    """Send each CSS their unsent digest entries. Returns how many digests went out.

    Entries are marked sent, so a second run sends nothing. A day with only time-sensitive
    emails, which the CSS already has, sends no digest.
    """
    from .notifications import EmailSupportDailyDigest

    now = now or timezone.now()
    entries = (
        SupportDigestEntry.objects.filter(daily_sent_at__isnull=True, created__lt=now)
        .select_related("user", "chapter")
        .order_by("user_id", "chapter__name", "created", "pk")
    )
    sent = 0
    for user, user_entries in groupby(entries, key=attrgetter("user")):
        user_entries = list(user_entries)
        wanted = user.is_active and bool(user.email) and any(not entry.realtime for entry in user_entries)
        if dry_run:
            sent += wanted
            continue
        if wanted:
            EmailSupportDailyDigest(user, user_entries, now).send(user=user)
            sent += 1
        SupportDigestEntry.objects.filter(pk__in=[entry.pk for entry in user_entries]).update(daily_sent_at=now)
    return sent


def daily_sections(entries):
    """Digest-only emails grouped by chapter, then the time-sensitive ones already sent."""
    sections = []
    for chapter, chapter_entries in groupby(entries, key=attrgetter("chapter")):
        emails = [entry for entry in chapter_entries if not entry.realtime]
        if emails:
            sections.append({"chapter": chapter, "url": chapter_url(chapter), "emails": emails})
    already_sent = [entry for entry in entries if entry.realtime]
    return sections, already_sent


def send_monthly_digests(today=None, dry_run=False, force=False):
    """Send each current CSS a summary of last month for each chapter. Returns the count.

    A CSS who already got this month's digest is skipped unless ``force``.
    """
    from .notifications import EmailSupportMonthlyDigest

    today = today or timezone.localdate()
    period_start, period_end = previous_month_period(today)
    month_start = period_end + datetime.timedelta(days=1)
    sent = 0
    for user in current_css_users(on=today):
        if not user.is_active or not user.email:
            continue
        if not force and _monthly_already_sent(user, month_start):
            continue
        entries = list(
            SupportDigestEntry.objects.filter(
                user=user, created__date__gte=period_start, created__date__lte=period_end
            ).select_related("chapter")
        )
        chapters = {chapter.pk: chapter for chapter in css_chapters(user)}
        chapters.update({entry.chapter_id: entry.chapter for entry in entries})
        if not chapters:
            continue
        if dry_run:
            sent += 1
            continue
        sections = [
            chapter_month_summary(chapter, [entry for entry in entries if entry.chapter_id == chapter.pk], today)
            for chapter in sorted(chapters.values(), key=attrgetter("name"))
        ]
        if EmailSupportMonthlyDigest(user, period_start, sections).send(user=user):
            sent += 1
            SupportDigestEntry.objects.filter(pk__in=[entry.pk for entry in entries]).update(
                monthly_sent_at=timezone.now()
            )
    return sent


def _monthly_already_sent(user, month_start):
    from .notifications import EmailSupportMonthlyDigest

    return SentNotification.objects.filter(
        notification_class=EmailSupportMonthlyDigest.get_class_path(),
        user=user,
        status=SentNotification.STATUS_SUCCESS,
        date_sent__date__gte=month_start,
    ).exists()


def chapter_month_summary(chapter, entries, today):
    """Last month's emails and what is still open for one chapter."""
    from thetatauCMT.ballots.models import Ballot
    from thetatauCMT.tasks.models import TaskDate

    officers = chapter.get_current_officers_council_specific()
    overdue = TaskDate.incomplete_dates_for_chapter(chapter).filter(date__lt=today).select_related("task")
    open_ballots = [
        ballot for ballot in Ballot.chapter_ballots(chapter).filter(due_date__gte=today) if not ballot["motion"]
    ]
    return {
        "chapter": chapter,
        "url": chapter_url(chapter),
        "emails": sorted(entries, key=attrgetter("created")),
        "missing_officers": [title for title, officer in zip(OFFICER_TITLES, officers) if officer is None],
        "overdue_tasks": list(overdue.order_by("date")[:10]),
        "overdue_count": overdue.count(),
        "open_ballots": sorted(open_ballots, key=lambda ballot: ballot["due_date"]),
    }
