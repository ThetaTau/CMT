"""The competition's emails (the spec's Email inventory, E1 to E10).

The services decide who gets what and when; these classes only render what they are given.
Chapter emails reach the chapter's Chapter Support Specialists through ``SupportCopyMixin``
(S21), and replies go to the competition contact (Q13). Emails link to CMT pages, never to a
file, so the CMT checks who is asking before it shows one (Q11 B).
"""

import logging

from django.conf import settings
from django.urls import reverse
from herald import registry
from herald.base import EmailNotification

from thetatauCMT.support.emails import SupportCopyMixin
from thetatauCMT.support.models import SupportDigestEntry

from . import services
from .models import Entry, Judge, NotificationLog, Participant, Round

logger = logging.getLogger(__name__)
Kind = NotificationLog.Kind


def absolute(name, *args):
    return settings.CURRENT_URL + reverse(name, args=args)


def round_windows(competition):
    """Each round's window, for emails and pages: name, opening and deadline in the competition's zone."""
    return [
        {
            "name": round_.name,
            "opens": competition.format_time(round_.opens_at),
            "closes": competition.format_time(round_.closes_at),
            "qualifiers_only": round_.eligibility == Round.Eligibility.ADVANCED,
        }
        for round_ in competition.rounds.all()
    ]


def due_phrase(days_left):
    if days_left <= 0:
        return "today"
    if days_left == 1:
        return "tomorrow"
    return f"in {days_left} days"


class CompetitionEmail(SupportCopyMixin, EmailNotification):
    """Shared set-up: recipients, reply-to, the subject prefix and the common context."""

    render_types = ["html"]

    def setup(self, competition, to_emails, subject, context, chapter=None, link=""):
        contact = services.competition_contact(competition)
        self.to_emails = list(to_emails)
        self.cc = []
        self.reply_to = [contact.email]
        self.subject = f"{competition.short_name}: {subject}"
        self.support_chapter = chapter
        self.support_kind = SupportDigestEntry.Kind.CASE_COMPETITION if chapter is not None else None
        self.support_link = link
        self.context = {
            "competition": competition,
            "competition_url": absolute("competitions:detail", competition.slug),
            "contact_name": contact.name,
            "reply_email": contact.email,
            "host": settings.CURRENT_URL,
            **context,
        }


@registry.register_decorator()
class CompetitionWelcome(CompetitionEmail):
    """E1: a chapter registered itself, with the intent form or its first submission."""

    template_name = "competition_welcome"

    def __init__(self, participant):
        competition, chapter = participant.competition, participant.chapter
        intent_url = absolute("competitions:intent", competition.slug)
        self.setup(
            competition,
            services.chapter_recipients(chapter, competition),
            f"{chapter.full_name} is registered",
            {
                "chapter": chapter,
                "participant": participant,
                "contacts": list(participant.contacts.order_by("name")),
                "windows": round_windows(competition),
                "key_dates": list(competition.key_dates.all()),
                "intent_url": intent_url,
            },
            chapter=chapter,
            link=intent_url,
        )

    @staticmethod
    def get_demo_args():
        return [Participant.objects.order_by("?").first()]


@registry.register_decorator()
class ChapterReminder(CompetitionEmail):
    """E2, E3 and E4: the window opens soon, is open, or closes soon, to a chapter that has not submitted."""

    template_name = "competition_chapter_reminder"

    def __init__(self, round_, chapter, kind, now=None):
        competition = round_.competition
        now = services._now(now)
        entry = services.entry_for(round_, chapter)
        deadline = services.deadline_for(round_, entry)
        days_left = (competition.local(deadline).date() - competition.local(now).date()).days
        opens = competition.format_time(round_.opens_at)
        due = competition.format_time(deadline)
        if kind == Kind.OPENS_SOON:
            local_open = competition.local(round_.opens_at)
            subject = f"The {round_.name} window opens {local_open:%A, %B} {local_open.day}"
        elif kind == Kind.OPEN:
            subject = f"The {round_.name} window is open until {due}"
        else:
            subject = f"{round_.name} due {due_phrase(days_left)}, {due}"
        submit_url = absolute("competitions:submit", competition.slug, round_.number)
        participant = services.participant_for(competition, chapter)
        self.setup(
            competition,
            services.chapter_recipients(chapter, competition),
            subject,
            {
                "round": round_,
                "chapter": chapter,
                "kind": kind,
                "opens": opens,
                "due": due,
                "due_phrase": due_phrase(days_left),
                "extended": deadline != round_.closes_at,
                "status": services.ENTRY_STATUS_LABELS[services.entry_status(entry, round_, now)],
                "missing": services.missing_items(entry, round_),
                "items": list(round_.items.all()),
                "submit_url": submit_url,
                "intent_url": absolute("competitions:intent", competition.slug),
                "contacts": list(participant.contacts.order_by("name")) if participant else [],
                "qualifiers_only": round_.eligibility == Round.Eligibility.ADVANCED,
            },
            chapter=chapter,
            link=submit_url,
        )

    @staticmethod
    def get_demo_args():
        round_ = Round.objects.order_by("?").first()
        participant = Participant.objects.filter(competition_id=getattr(round_, "competition_id", None)).first()
        return [round_, getattr(participant, "chapter", None), Kind.CLOSES_SOON]


@registry.register_decorator()
class EntryReceipt(CompetitionEmail):
    """E5: a save left the entry complete; to whoever saved it and the chapter."""

    template_name = "competition_receipt"

    def __init__(self, entry, saved_by=None):
        round_, chapter = entry.round, entry.chapter
        competition = round_.competition
        files = services.current_files(entry)
        rows = [
            {"label": item.label, "name": files[item.pk].original_name or files[item.pk].link or "None"}
            for item in round_.items.all()
            if item.pk in files
        ]
        entry_url = absolute("competitions:entry", entry.public_id)
        to = services.chapter_recipients(chapter, competition)
        if saved_by is not None and saved_by.email:
            to = services._unique_emails([saved_by.email, *to])
        self.setup(
            competition,
            to,
            f"{round_.name} received from {chapter.full_name}",
            {
                "round": round_,
                "chapter": chapter,
                "entry": entry,
                "files": rows,
                "team": list(entry.team.select_related("user")),
                "saved_by": saved_by,
                "saved_at": competition.format_time(entry.last_saved_at),
                "on_behalf": entry.last_saved_on_behalf,
                "due": competition.format_time(services.deadline_for(round_, entry)),
                "entry_url": entry_url,
                "submit_url": absolute("competitions:submit", competition.slug, round_.number),
            },
            chapter=chapter,
            link=entry_url,
        )

    @staticmethod
    def get_demo_args():
        entry = Entry.objects.filter(submitted_at__isnull=False).order_by("?").first()
        return [entry, getattr(entry, "last_saved_by", None)]


@registry.register_decorator()
class WindowClosedSummary(CompetitionEmail):
    """E6: the window has closed; to the managers."""

    template_name = "competition_closed_summary"

    def __init__(self, round_, to_emails):
        competition = round_.competition
        complete, waiting, extended = services.round_progress(round_)
        manage_url = absolute("competitions:manage", competition.slug)
        self.setup(
            competition,
            to_emails,
            f"The {round_.name} window has closed: {len(complete)} submitted",
            {
                "round": round_,
                "closed": competition.format_time(round_.closes_at),
                "complete": complete,
                "waiting": waiting,
                "extended": [
                    {"chapter": entry.chapter, "until": competition.format_time(services.deadline_for(round_, entry))}
                    for entry in extended
                ],
                "manage_url": manage_url,
            },
        )

    @staticmethod
    def get_demo_args():
        round_ = Round.objects.order_by("?").first()
        return [round_, ["demo@example.com"]]


@registry.register_decorator()
class JudgeNotice(CompetitionEmail):
    """E7 (judging is open) and E8 (scorecards due), to one judge."""

    template_name = "competition_judge_notice"

    def __init__(self, judge, kind, to_do, assigned, now=None):
        round_ = judge.round
        competition = round_.competition
        now = services._now(now)
        deadline = round_.judging_closes_at
        days_left = None
        if deadline is not None:
            days_left = (competition.local(deadline).date() - competition.local(now).date()).days
        if kind == Kind.JUDGING_OPEN:
            subject = f"{round_.name} judging is open: {assigned} to score"
        else:
            subject = f"{round_.name} scorecards due {due_phrase(days_left or 0)}: {to_do} still to do"
        self.setup(
            competition,
            [judge.user.email] if judge.user.email else [],
            subject,
            {
                "round": round_,
                "judge": judge,
                "kind": kind,
                "to_do": to_do,
                "assigned": assigned,
                "deadline": competition.format_time(deadline),
                "due_phrase": due_phrase(days_left or 0),
                "judging_url": absolute("competitions:judging"),
            },
        )

    @staticmethod
    def get_demo_args():
        judge = Judge.objects.order_by("?").first()
        return [judge, Kind.JUDGING_OPEN, 3, 5]


@registry.register_decorator()
class ChapterResult(CompetitionEmail):
    """E9: a round's results are published; to each chapter with an entry in it."""

    template_name = "competition_results"

    def __init__(self, entry):
        round_, chapter = entry.round, entry.chapter
        competition = round_.competition
        entry_url = absolute("competitions:entry", entry.public_id)
        if not entry.eligible:
            outcome = "not eligible"
        elif entry.advanced:
            outcome = "qualified"
        else:
            outcome = "not selected"
        following = services.next_round(round_)
        self.setup(
            competition,
            services.chapter_recipients(chapter, competition),
            f"{round_.name} results for {chapter.full_name}",
            {
                "round": round_,
                "chapter": chapter,
                "entry": entry,
                "outcome": outcome,
                "feedback_shared": round_.share_feedback,
                "entry_url": entry_url,
                "results_url": absolute("competitions:results", competition.slug, round_.number),
                "next_round": following,
                "next_round_opens": competition.format_time(following.opens_at) if following else "",
            },
            chapter=chapter,
            link=entry_url,
        )

    @staticmethod
    def get_demo_args():
        return [Entry.objects.filter(round__results_published_at__isnull=False).order_by("?").first()]


@registry.register_decorator()
class WinnersAnnounced(CompetitionEmail):
    """E10: the winners are announced; to each finalist chapter."""

    template_name = "competition_winners"

    def __init__(self, entry, winners):
        round_, chapter = entry.round, entry.chapter
        competition = round_.competition
        results_url = absolute("competitions:results", competition.slug, round_.number)
        self.setup(
            competition,
            services.chapter_recipients(chapter, competition),
            f"The {competition.name} winners",
            {
                "round": round_,
                "chapter": chapter,
                "entry": entry,
                "winners": winners,
                "feedback_shared": round_.share_feedback,
                "entry_url": absolute("competitions:entry", entry.public_id),
                "results_url": results_url,
            },
            chapter=chapter,
            link=results_url,
        )

    @staticmethod
    def get_demo_args():
        entry = Entry.objects.filter(place__isnull=False).order_by("?").first()
        return [entry, [entry] if entry else []]


def send_once(email, key, kind, competition, round_=None, chapter=None, user=None, now=None):
    """Send ``email`` unless ``key`` is in the log; log it once it is sent (a failed send is tried again)."""
    if services.already_sent(key) or not email.to_emails:
        return False
    if not email.send():
        logger.warning("Case Competition email %s was not sent", key)
        return False
    services.record_sent(key, kind, competition, round_, chapter, user, email.to_emails, now=now)
    return True


def welcome_key(competition_id, chapter_id):
    return f"welcome:{competition_id}:{chapter_id}"


def send_welcome(participant_id):
    """E1, once per chapter and competition; called once the registration commits."""
    participant = Participant.objects.select_related("competition", "chapter").filter(pk=participant_id).first()
    if participant is None or participant.withdrawn_at is not None:
        return False
    competition, chapter = participant.competition, participant.chapter
    return send_once(
        CompetitionWelcome(participant),
        welcome_key(competition.pk, chapter.pk),
        Kind.WELCOME,
        competition,
        chapter=chapter,
    )


def send_receipt(entry_id, saved_by_id=None):
    """E5, after every save that leaves the entry complete; called once the save commits. Not logged."""
    from thetatauCMT.users.models import User

    entry = Entry.objects.select_related("round__competition", "chapter").filter(pk=entry_id).first()
    if entry is None or not services.entry_is_complete(entry):
        return False
    saved_by = User.objects.filter(pk=saved_by_id).first() if saved_by_id else None
    email = EntryReceipt(entry, saved_by)
    if not email.to_emails:
        return False
    return email.send()
