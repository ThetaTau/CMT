"""NECCWI-7: the one daily command and the chapter reminder ladder (Q14, S30, S32)."""

import datetime

import pytest
from django.core import mail
from django.core.management import call_command

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.support.models import SupportDigestEntry
from thetatauCMT.support.tests.factories import ChapterSupportAssignmentFactory

from .. import reminders
from ..models import NotificationLog, Participant, Round
from .factories import (
    EntryFactory,
    EntryFileFactory,
    ParticipantFactory,
    RoundFactory,
    SubmissionItemFactory,
    eastern,
    give_role,
    member,
)

pytestmark = pytest.mark.django_db
Kind = NotificationLog.Kind


def morning(month, day, year=2026):
    """The daily run, at 9:00 am Eastern."""
    return eastern(year, month, day, 9)


@pytest.fixture
def round_():
    round_ = RoundFactory()
    SubmissionItemFactory(round=round_, label="Proposal")
    return round_


@pytest.fixture
def chapter(round_):
    chapter = ChapterFactory(name="alpha")
    ParticipantFactory(competition=round_.competition, chapter=chapter)
    return chapter


def run(day, dry_run=False):
    return reminders.send_scheduled(now=day, dry_run=dry_run)


def kinds():
    return list(NotificationLog.objects.order_by("sent_at", "pk").values_list("kind", flat=True))


def complete(round_, chapter):
    entry = EntryFactory(round=round_, chapter=chapter, summary="S", submitted_at=eastern(2026, 12, 5))
    EntryFileFactory(entry=entry, item=round_.items.get())
    return entry


def test_each_step_once_on_its_eastern_day(round_, chapter):
    give_role(member(ChapterFactory(name="delta"), status="alumni"), "professional development director")
    sent = {}
    day = datetime.date(2026, 11, 25)
    while day <= datetime.date(2026, 12, 13):
        before = len(mail.outbox)
        run(morning(day.month, day.day))
        run(morning(day.month, day.day))  # a second run the same day sends nothing
        sent[day] = [message.subject for message in mail.outbox[before:]]
        day += datetime.timedelta(days=1)
    days_with_email = {day.isoformat(): subjects for day, subjects in sent.items() if subjects}
    assert list(days_with_email) == [
        "2026-11-27",
        "2026-12-04",
        "2026-12-08",
        "2026-12-10",
        "2026-12-11",
        "2026-12-12",
    ]
    assert days_with_email["2026-11-27"] == ["NECC: The Proposal window opens Friday, December 4"]
    assert days_with_email["2026-12-04"] == [
        "NECC: The Proposal window is open until Fri, Dec 11, 2026, 11:59 pm Eastern"
    ]
    assert days_with_email["2026-12-08"] == ["NECC: Proposal due in 3 days, Fri, Dec 11, 2026, 11:59 pm Eastern"]
    assert days_with_email["2026-12-10"] == ["NECC: Proposal due tomorrow, Fri, Dec 11, 2026, 11:59 pm Eastern"]
    assert days_with_email["2026-12-11"] == ["NECC: Proposal due today, Fri, Dec 11, 2026, 11:59 pm Eastern"]
    assert days_with_email["2026-12-12"] == ["NECC: The Proposal window has closed: 0 submitted"]
    assert kinds() == [
        Kind.OPENS_SOON,
        Kind.OPEN,
        Kind.CLOSES_SOON,
        Kind.CLOSES_SOON,
        Kind.CLOSES_SOON,
        Kind.CLOSED_SUMMARY,
    ]


def test_only_chapters_without_a_complete_entry_and_not_withdrawn(round_, chapter):
    finished = ChapterFactory(name="beta")
    ParticipantFactory(competition=round_.competition, chapter=finished)
    complete(round_, finished)
    gone = ChapterFactory(name="epsilon")
    ParticipantFactory(competition=round_.competition, chapter=gone, withdrawn_at=eastern(2026, 11, 1))
    ChapterFactory(name="delta")  # not taking part
    run(morning(12, 8))
    assert NotificationLog.objects.get().chapter == chapter


def test_a_run_after_a_gap_sends_only_the_current_step(round_, chapter):
    run(morning(12, 10))
    assert kinds() == [Kind.CLOSES_SOON]
    assert NotificationLog.objects.get().key.endswith(":1:2026-12-11")


def test_moving_the_close_starts_the_closing_reminders_over(round_, chapter):
    run(morning(12, 4))
    run(morning(12, 8))
    assert kinds() == [Kind.OPEN, Kind.CLOSES_SOON]
    round_.closes_at = eastern(2026, 12, 18, 23, 59, 59)
    round_.save()
    run(morning(12, 9))  # the latest step reached is now the opening, already sent
    assert len(kinds()) == 2
    run(morning(12, 15))
    assert kinds() == [Kind.OPEN, Kind.CLOSES_SOON, Kind.CLOSES_SOON]
    assert NotificationLog.objects.latest("sent_at").key.endswith(":3:2026-12-18")


def test_an_extension_moves_one_chapters_reminders(round_, chapter):
    EntryFactory(round=round_, chapter=chapter, title="", deadline_override=eastern(2026, 12, 14, 23, 59))
    run(morning(12, 11))  # three days before the chapter's own deadline, not the round's "due today"
    assert NotificationLog.objects.get(kind=Kind.CLOSES_SOON).key.endswith(":3:2026-12-14")
    run(morning(12, 13))
    assert NotificationLog.objects.filter(kind=Kind.CLOSES_SOON).latest("sent_at").key.endswith(":1:2026-12-14")
    assert any("due tomorrow, Mon, Dec 14, 2026, 11:59 pm Eastern" in message.subject for message in mail.outbox)


def test_a_chapter_added_in_django_admin_gets_the_step_due_on_the_next_run(round_):
    run(morning(12, 4))
    late = ChapterFactory(name="beta")
    ParticipantFactory(competition=round_.competition, chapter=late, source=Participant.Source.ADMIN)
    run(morning(12, 5))
    log = NotificationLog.objects.get()
    assert (log.chapter, log.kind) == (late, Kind.OPEN)


def test_a_chapter_registered_just_before_skips_the_opens_soon_step(round_, chapter):
    from ..notifications import welcome_key

    NotificationLog.objects.create(
        key=welcome_key(round_.competition_id, chapter.pk),
        kind=Kind.WELCOME,
        competition=round_.competition,
        chapter=chapter,
        sent_at=eastern(2026, 11, 25),
    )
    run(morning(11, 27))
    assert kinds() == [Kind.WELCOME]
    run(morning(12, 4))
    assert kinds() == [Kind.WELCOME, Kind.OPEN]


def test_a_qualifiers_only_round_reminds_only_the_qualifiers(round_, chapter):
    other = ChapterFactory(name="beta")
    ParticipantFactory(competition=round_.competition, chapter=other)
    qualifier = complete(round_, chapter)
    qualifier.advanced = True
    qualifier.save()
    complete(round_, other)
    round_.results_published_at = eastern(2027, 1, 20)
    round_.save()
    final = RoundFactory(
        competition=round_.competition,
        number=2,
        name="Final submission",
        eligibility=Round.Eligibility.ADVANCED,
        selection=Round.Selection.PLACES,
        places=2,
        opens_at=eastern(2027, 5, 21),
        closes_at=eastern(2027, 5, 28, 23, 59, 59),
        judging_closes_at=eastern(2027, 6, 25, 23, 59, 59),
    )
    SubmissionItemFactory(round=final, label="Final report")
    run(morning(5, 14, 2027))
    log = NotificationLog.objects.get()
    assert (log.chapter, log.kind, log.round) == (chapter, Kind.OPENS_SOON, final)


def test_dry_run_sends_and_writes_nothing(round_, chapter):
    lines = run(morning(12, 4), dry_run=True)
    assert lines == [f"[dry-run] Would send E3 window is open: {round_} to {chapter}"]
    assert not mail.outbox and not NotificationLog.objects.exists()


def test_the_command(round_, chapter, freezer):
    freezer.move_to(morning(12, 4))
    call_command("case_competition_daily", "--dry-run")
    assert not mail.outbox
    call_command("case_competition_daily")
    assert len(mail.outbox) == 1 and kinds() == [Kind.OPEN]


def test_chapter_emails_reach_the_css_digest_and_reply_to_the_contact(round_, chapter):
    from thetatauCMT.support.services import clear_css_state

    assignment = ChapterSupportAssignmentFactory(chapter=chapter)
    clear_css_state(assignment.user)
    round_.competition.contact_email = "necc@example.com"
    round_.competition.save()
    run(morning(12, 4))
    entry = SupportDigestEntry.objects.get()
    assert (entry.user, entry.chapter, entry.kind) == (
        assignment.user,
        chapter,
        SupportDigestEntry.Kind.CASE_COMPETITION,
    )
    assert mail.outbox[0].reply_to == ["necc@example.com"]


def test_the_contact_setting_answers_every_email(round_, chapter):
    from .. import services
    from .factories import set_config

    set_config(services.CONTACT_CONFIG_KEY, "case.competition@example.com")
    run(morning(12, 4))
    message = mail.outbox[0]
    assert message.reply_to == ["case.competition@example.com"]
    footer = " ".join(message.alternatives[0][0].split())
    assert "reach the competition contact, at case.competition@example.com" in footer


def test_unpublished_competitions_send_nothing(round_, chapter):
    round_.competition.is_published = False
    round_.competition.save()
    run(morning(12, 4))
    assert not NotificationLog.objects.exists()
