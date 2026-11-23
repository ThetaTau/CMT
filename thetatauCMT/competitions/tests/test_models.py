import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import RestrictedError
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory

from ..models import (
    CriterionScore,
    Entry,
    EntryFile,
    NotificationLog,
    Participant,
    Round,
    Scorecard,
    entry_file_path,
    parse_days,
    validate_days,
)
from .factories import (
    CompetitionFactory,
    CriterionScoreFactory,
    EntryFactory,
    EntryFileFactory,
    ParticipantFactory,
    RoundFactory,
    eastern,
)

pytestmark = pytest.mark.django_db


def refused(make):
    with pytest.raises(IntegrityError), transaction.atomic():
        make()


def test_a_chapter_registers_once_per_competition():
    participant = ParticipantFactory()
    refused(lambda: Participant.objects.create(competition=participant.competition, chapter=participant.chapter))


def test_a_chapter_has_one_entry_per_round():
    entry = EntryFactory()
    refused(lambda: Entry.objects.create(round=entry.round, chapter=entry.chapter))


def test_each_item_has_one_current_file_and_keeps_the_replaced_ones():
    current = EntryFileFactory()
    refused(lambda: EntryFile.objects.create(entry=current.entry, item=current.item, link="https://example.com/2"))

    current.replaced_at = timezone.now()
    current.save()
    EntryFile.objects.create(entry=current.entry, item=current.item, link="https://example.com/2")

    assert current.entry.files.count() == 2
    assert current.entry.files.filter(replaced_at__isnull=True).count() == 1


def test_a_file_row_needs_a_file_or_a_link():
    entry_file = EntryFileFactory()
    refused(lambda: EntryFile.objects.create(entry=entry_file.entry, item=entry_file.item, link="", replaced_at=None))


def test_one_scorecard_per_assignment_and_one_score_per_criterion():
    score = CriterionScoreFactory()
    refused(lambda: Scorecard.objects.create(assignment=score.scorecard.assignment))
    refused(lambda: CriterionScore.objects.create(scorecard=score.scorecard, criterion=score.criterion, points=3))


def test_uploads_and_scores_keep_their_item_and_criterion_unless_the_whole_competition_goes():
    entry_file = EntryFileFactory()
    score = CriterionScoreFactory(scorecard__assignment__entry=entry_file.entry)
    with pytest.raises(RestrictedError), transaction.atomic():
        entry_file.item.delete()
    with pytest.raises(RestrictedError), transaction.atomic():
        score.criterion.delete()
    entry_file.entry.round.competition.delete()
    assert not EntryFile.objects.exists() and not CriterionScore.objects.exists()


def test_a_window_closes_after_it_opens_and_judging_ends_after_the_close():
    refused(lambda: RoundFactory(closes_at=eastern(2026, 12, 3)))
    refused(lambda: RoundFactory(judging_closes_at=eastern(2026, 12, 11, 12)))


def test_round_numbers_are_unique_within_a_competition():
    proposal = RoundFactory()
    refused(lambda: RoundFactory(competition=proposal.competition, number=1, name="Again"))


def test_each_place_goes_to_one_entry():
    first = EntryFactory(chapter=ChapterFactory(name="alpha"), place=1)
    EntryFactory(round=first.round, chapter=ChapterFactory(name="beta"), place=2)
    refused(lambda: EntryFactory(round=first.round, chapter=ChapterFactory(name="delta"), place=1))
    refused(lambda: EntryFactory(round=first.round, chapter=ChapterFactory(name="epsilon"), place=0))


def test_the_intent_form_closes_after_it_opens():
    refused(lambda: CompetitionFactory(intent_opens_at=eastern(2026, 9, 28), intent_closes_at=eastern(2026, 9, 11)))


def test_the_same_email_is_logged_once():
    competition = CompetitionFactory()
    NotificationLog.objects.create(key="open:1:2:2026-12-04", kind=NotificationLog.Kind.OPEN, competition=competition)
    refused(
        lambda: NotificationLog.objects.create(
            key="open:1:2:2026-12-04", kind=NotificationLog.Kind.OPEN, competition=competition
        )
    )


def test_round_settings_that_cannot_work_are_explained():
    first_round = RoundFactory.build(
        number=1, eligibility=Round.Eligibility.ADVANCED, selection=Round.Selection.PLACES, places=None
    )
    with pytest.raises(ValidationError) as error:
        first_round.clean()
    assert set(error.value.message_dict) == {"eligibility", "places"}

    backwards = RoundFactory.build(closes_at=eastern(2026, 12, 3), judging_closes_at=eastern(2026, 12, 1))
    with pytest.raises(ValidationError) as error:
        backwards.clean()
    assert set(error.value.message_dict) == {"closes_at", "judging_closes_at"}


def test_the_contact_is_a_national_officer_role():
    competition = CompetitionFactory.build(contact_role=" Professional Development Director ")
    competition.clean()
    assert competition.contact_role == "professional development director"

    competition.contact_role = "pd chair"
    with pytest.raises(ValidationError) as error:
        competition.clean()
    assert "contact_role" in error.value.message_dict


def test_only_active_chapters_can_be_added():
    closed = Participant(competition=CompetitionFactory(), chapter=ChapterFactory(name="delta", active=False))
    with pytest.raises(ValidationError) as error:
        closed.clean()
    assert "chapter" in error.value.message_dict


def test_scores_stay_between_the_lowest_and_highest_score():
    score = CriterionScoreFactory(points=5)
    score.clean()
    for points in (0, 6):
        score.points = points
        with pytest.raises(ValidationError):
            score.clean()
    score.points = None
    score.clean()


def test_times_read_in_the_competition_time_zone():
    competition = CompetitionFactory.build()
    proposal_close = datetime.datetime(2026, 12, 12, 4, 59, 59, tzinfo=datetime.timezone.utc)

    assert competition.format_time(proposal_close) == "Fri, Dec 11, 2026, 11:59 pm Eastern"
    assert competition.format_time(eastern(2026, 12, 4)) == "Fri, Dec 4, 2026, 12:00 am Eastern"
    assert competition.format_time(None) == "None"

    competition.time_zone = "America/Los_Angeles"
    assert competition.format_time(proposal_close) == "Fri, Dec 11, 2026, 8:59 pm Pacific"


def test_reminder_days_allow_spaces_and_refuse_anything_else():
    assert parse_days("3, 1, 0") == [3, 1, 0]
    assert parse_days("") == []
    validate_days("3, 1, 0")
    for value in ("3,,1", "two", "-1", "1.5"):
        with pytest.raises(ValidationError):
            validate_days(value)


def test_uploads_go_in_a_random_folder_and_keep_their_name():
    entry = EntryFactory(round__competition__slug="necc-2026-2027", chapter=ChapterFactory(name="alpha"))

    first = entry_file_path(EntryFile(entry=entry), "Our Proposal (final).PDF")
    second = entry_file_path(EntryFile(entry=entry), "Our Proposal (final).PDF")

    assert first.startswith("competitions/necc-2026-2027/round-1/alpha/")
    assert first.endswith("/Our_Proposal_final.pdf")
    assert len(first.split("/")[4]) == 32
    assert first != second
    assert entry_file_path(EntryFile(entry=entry), "..").endswith("/file")
