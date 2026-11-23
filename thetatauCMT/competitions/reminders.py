"""Everything the one daily command does (Q14, NECCWI-7): the competition's scheduled emails.

Each chapter reminder is a step on a ladder: before the window opens (E2), when it opens (E3)
and as it closes (E4). Only the most recent step already reached is sent, once, so a run after
a missed day never replays old steps. Each step's key in the email log includes the date it
counts from, so moving a window starts its reminders over from the step due on the new date
without repeating one (S32). Days are calendar days in the competition's time zone. The
managers' summary (E6) follows the close, and ``judging.py`` adds the judges' emails.
"""

import datetime
from dataclasses import dataclass

from thetatauCMT.chapters.models import Chapter

from . import services
from .models import NotificationLog, Round, parse_days
from .notifications import ChapterReminder, WindowClosedSummary, send_once, welcome_key

Kind = NotificationLog.Kind
# A chapter that registered itself this many days before a "window opens soon" step skips it (E2).
WELCOME_QUIET_DAYS = 3
# The managers' summary is never sent for a window that closed longer ago than this.
SUMMARY_STALE_DAYS = 14
LABELS = {
    Kind.OPENS_SOON: "E2 window opens soon",
    Kind.OPEN: "E3 window is open",
    Kind.CLOSES_SOON: "E4 window closes soon",
    Kind.CLOSED_SUMMARY: "E6 window closed summary",
    Kind.JUDGING_OPEN: "E7 judging is open",
    Kind.JUDGING_DUE: "E8 scorecards due",
}


@dataclass(frozen=True)
class Step:
    """One rung of a reminder ladder: reached at ``reached_at``, current until ``until``."""

    kind: str
    days: object
    reached_at: datetime.datetime
    until: datetime.datetime
    counted_from: datetime.date

    def key(self, round_, subject_id):
        days = "" if self.days is None else f":{self.days}"
        return f"{self.kind}:{round_.pk}:{subject_id}{days}:{self.counted_from.isoformat()}"


def start_of_day(day, zone):
    return datetime.datetime.combine(day, datetime.time.min, tzinfo=zone)


def chapter_steps(round_, deadline):
    """The chapter reminder ladder for one deadline: the round's close, or a chapter's extension."""
    competition = round_.competition
    zone = competition.zone
    opens_day = competition.local(round_.opens_at).date()
    due_day = competition.local(deadline).date()
    steps = []
    for days in sorted(set(parse_days(round_.reminder_days_before_open)), reverse=True):
        reached_at = start_of_day(opens_day - datetime.timedelta(days=days), zone)
        if reached_at < round_.opens_at:
            steps.append(Step(Kind.OPENS_SOON, days, reached_at, round_.opens_at, opens_day))
    steps.append(Step(Kind.OPEN, None, round_.opens_at, deadline, opens_day))
    for days in sorted(set(parse_days(round_.reminder_days_before_close)), reverse=True):
        day = due_day - datetime.timedelta(days=days)
        # The "window is open" email covers the opening day (Round lifecycle).
        if day > opens_day:
            steps.append(Step(Kind.CLOSES_SOON, days, start_of_day(day, zone), deadline, due_day))
    return steps


def judge_steps(round_):
    """The judges' "scorecards due" ladder (E8), counting down to the judging deadline."""
    deadline = round_.judging_closes_at
    if deadline is None:
        return []
    competition = round_.competition
    due_day = competition.local(deadline).date()
    opened = round_.closes_at + services.grace(round_)
    steps = []
    for days in sorted(set(parse_days(round_.judge_reminder_days)), reverse=True):
        reached_at = start_of_day(due_day - datetime.timedelta(days=days), competition.zone)
        steps.append(Step(Kind.JUDGING_DUE, days, max(reached_at, opened), deadline, due_day))
    return steps


def current_step(steps, now):
    """The most recent step already reached and still current, or None."""
    reached = [step for step in steps if step.reached_at <= now < step.until]
    return max(reached, key=lambda step: step.reached_at) if reached else None


def _welcomed_recently(competition, chapter, step):
    since = step.reached_at - datetime.timedelta(days=WELCOME_QUIET_DAYS)
    return NotificationLog.objects.filter(key=welcome_key(competition.pk, chapter.pk), sent_at__gte=since).exists()


class Run:
    """One run of the daily command: what it sent, or would send with ``dry_run``."""

    def __init__(self, now, dry_run):
        self.now = now
        self.dry_run = dry_run
        self.lines = []

    def send(self, email_factory, key, kind, competition, round_=None, chapter=None, user=None, to_label=""):
        """Send once per key; with ``dry_run`` only report. ``email_factory`` builds the email when needed."""
        if services.already_sent(key):
            return False
        label = f"{LABELS.get(kind, kind)}: {to_label}".rstrip(": ")
        if self.dry_run:
            self.lines.append(f"[dry-run] Would send {label}")
            return True
        email = email_factory()
        if send_once(email, key, kind, competition, round_, chapter, user, now=self.now):
            self.lines.append(f"Sent {label} ({len(email.to_emails)} recipient(s))")
            return True
        return False


def send_chapter_reminders(round_, run):
    """E2, E3 and E4 to each chapter the round reminds that has no complete entry."""
    competition = round_.competition
    eligible = services.eligible_chapter_ids(round_)
    if not eligible:
        return
    entries = {
        entry.chapter_id: entry for entry in services.entries_with_files(round_.entries.filter(chapter_id__in=eligible))
    }
    for chapter in Chapter.objects.filter(pk__in=eligible).order_by("name"):
        entry = entries.get(chapter.pk)
        if entry is not None and services.entry_is_complete(entry):
            continue
        step = current_step(chapter_steps(round_, services.deadline_for(round_, entry)), run.now)
        if step is None:
            continue
        if step.kind == Kind.OPENS_SOON and _welcomed_recently(competition, chapter, step):
            continue
        run.send(
            lambda: ChapterReminder(round_, chapter, step.kind, run.now),
            step.key(round_, chapter.pk),
            step.kind,
            competition,
            round_,
            chapter,
            to_label=f"{round_} to {chapter}",
        )


def send_closed_summary(round_, run):
    """E6 to the managers, on the first run after the window (and its grace minutes) closed."""
    competition = round_.competition
    closed_at = round_.closes_at + services.grace(round_)
    if not closed_at <= run.now < round_.closes_at + datetime.timedelta(days=SUMMARY_STALE_DAYS):
        return
    key = f"{Kind.CLOSED_SUMMARY}:{round_.pk}:{competition.local(round_.closes_at).date().isoformat()}"
    run.send(
        lambda: WindowClosedSummary(round_, services.manager_emails(competition)),
        key,
        Kind.CLOSED_SUMMARY,
        competition,
        round_,
        to_label=f"{round_} to the managers",
    )


def send_scheduled(now=None, dry_run=False):
    """Every scheduled competition email due now, each sent once. Returns what was sent, as lines."""
    from . import judging

    run = Run(services._now(now), dry_run)
    rounds = (
        Round.objects.filter(competition__is_published=True, results_published_at__isnull=True)
        .select_related("competition")
        .prefetch_related("items")
        .order_by("competition_id", "number")
    )
    for round_ in rounds:
        send_chapter_reminders(round_, run)
        send_closed_summary(round_, run)
        judging.daily(round_, run)
    return run.lines
