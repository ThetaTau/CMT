import datetime

import pytest
from django.core.exceptions import ValidationError

from thetatauCMT.awards.models import AwardCycle
from thetatauCMT.awards.services import (
    MULTIPLE_NOMINATION_MSG,
    SINGLE_WINNER_MSG,
    check_nomination_allowed,
    check_winner_allowed,
    resolve_current_cycle,
)
from thetatauCMT.awards.tests.factories import AwardCycleFactory, AwardTypeFactory
from thetatauCMT.events.tests.factories import EventFactory

pytestmark = pytest.mark.django_db

TODAY = datetime.date(2026, 6, 15)


def _days(n):
    return TODAY + datetime.timedelta(days=n)


# ---------------------------------------------------------------------------
# Acceptance: cycle creation
# ---------------------------------------------------------------------------
def test_cycle_creation_persists_fields():
    cycle = AwardCycleFactory.create(
        name="Fall 2025",
        period_type=AwardCycle.PeriodType.TERM,
        start_date=datetime.date(2025, 8, 1),
        end_date=datetime.date(2025, 12, 31),
    )
    reloaded = AwardCycle.objects.get(pk=cycle.pk)
    assert reloaded.name == "Fall 2025"
    assert reloaded.period_type == "term"
    assert reloaded.start_date == datetime.date(2025, 8, 1)
    assert reloaded.end_date == datetime.date(2025, 12, 31)
    assert str(reloaded) == "Fall 2025"


def test_cycle_open_ended_end_date_nullable():
    cycle = AwardCycleFactory.create(start_date=datetime.date(2025, 1, 1), end_date=None)
    assert cycle.end_date is None
    assert cycle.contains(datetime.date(2999, 1, 1)) is True


def test_cycle_can_link_to_event():
    event = EventFactory.create()
    cycle = AwardCycleFactory.create(period_type=AwardCycle.PeriodType.EVENT, event=event)
    reloaded = AwardCycle.objects.get(pk=cycle.pk)
    assert reloaded.event_id == event.pk
    assert list(event.award_cycles.all()) == [cycle]


def test_cycle_clean_rejects_end_before_start():
    cycle = AwardCycleFactory.build(
        start_date=datetime.date(2025, 12, 31),
        end_date=datetime.date(2025, 1, 1),
    )
    with pytest.raises(ValidationError):
        cycle.clean()


def test_cycle_contains_is_inclusive_of_bounds():
    cycle = AwardCycleFactory.create(
        start_date=datetime.date(2025, 1, 1),
        end_date=datetime.date(2025, 12, 31),
    )
    assert cycle.contains(datetime.date(2025, 1, 1)) is True
    assert cycle.contains(datetime.date(2025, 12, 31)) is True
    assert cycle.contains(datetime.date(2024, 12, 31)) is False
    assert cycle.contains(datetime.date(2026, 1, 1)) is False


# ---------------------------------------------------------------------------
# Acceptance: current-cycle resolution
# ---------------------------------------------------------------------------
def test_resolve_current_cycle_returns_active_cycle():
    active = AwardCycleFactory.create(start_date=_days(-10), end_date=_days(10))
    AwardCycleFactory.create(start_date=_days(-100), end_date=_days(-50))  # past
    assert resolve_current_cycle(on_date=TODAY) == active


def test_resolve_current_cycle_open_ended():
    active = AwardCycleFactory.create(start_date=_days(-5), end_date=None)
    assert resolve_current_cycle(on_date=TODAY) == active


def test_resolve_current_cycle_prefers_most_recent_start():
    AwardCycleFactory.create(start_date=_days(-100), end_date=None)
    newer = AwardCycleFactory.create(start_date=_days(-1), end_date=None)
    assert resolve_current_cycle(on_date=TODAY) == newer


def test_resolve_current_cycle_period_type_filter():
    year = AwardCycleFactory.create(period_type=AwardCycle.PeriodType.YEAR, start_date=_days(-100), end_date=None)
    term = AwardCycleFactory.create(period_type=AwardCycle.PeriodType.TERM, start_date=_days(-10), end_date=None)
    assert resolve_current_cycle(on_date=TODAY, period_type="year") == year
    assert resolve_current_cycle(on_date=TODAY, period_type="term") == term


def test_resolve_current_cycle_none_when_no_active_cycle():
    AwardCycleFactory.create(start_date=_days(-100), end_date=_days(-50))
    assert resolve_current_cycle(on_date=TODAY) is None


# ---------------------------------------------------------------------------
# Acceptance: single-winner enforcement per cycle
# ---------------------------------------------------------------------------
def test_single_winner_award_allows_only_one_winner():
    award = AwardTypeFactory.create(single_winner=True)
    assert award.winner_limit == 1
    assert award.can_add_winner(0) is True
    assert award.can_add_winner(1) is False
    check_winner_allowed(award, 0)  # first winner is fine
    with pytest.raises(ValidationError) as exc:
        check_winner_allowed(award, 1)
    assert SINGLE_WINNER_MSG in str(exc.value)


# ---------------------------------------------------------------------------
# Acceptance: multiple-winner allowed when configured
# ---------------------------------------------------------------------------
def test_multiple_winner_award_allows_many():
    award = AwardTypeFactory.create(single_winner=False, allow_multiple_winners=True)
    assert award.winner_limit is None
    assert award.can_add_winner(0) is True
    assert award.can_add_winner(25) is True
    check_winner_allowed(award, 25)  # no raise


# ---------------------------------------------------------------------------
# Multiple-nomination rule (also configured on AwardType per AWI-2)
# ---------------------------------------------------------------------------
def test_multiple_nomination_rule():
    single = AwardTypeFactory.create(allow_multiple_nominations=False)
    assert single.can_add_nomination(0) is True
    assert single.can_add_nomination(1) is False
    with pytest.raises(ValidationError) as exc:
        check_nomination_allowed(single, 1)
    assert MULTIPLE_NOMINATION_MSG in str(exc.value)

    multi = AwardTypeFactory.create(allow_multiple_nominations=True)
    assert multi.can_add_nomination(3) is True
    check_nomination_allowed(multi, 3)  # no raise
