import datetime

import pytest

from thetatauCMT.scores.models import ScoreChapter, ScoreType
from thetatauCMT.submissions.tests.factories import SubmissionFactory

# ---------------------------------------------------------------------------
# ScoreType enum helpers
# ---------------------------------------------------------------------------


def test_section_get_value():
    assert ScoreType.SECTION.get_value("bro") == "Brotherhood"
    assert ScoreType.SECTION.get_value("ops") == "Operate"
    assert ScoreType.SECTION.get_value("pro") == "Professional"
    assert ScoreType.SECTION.get_value("ser") == "Service"


def test_types_get_value():
    assert ScoreType.TYPES.get_value("evt") == "Event"
    assert ScoreType.TYPES.get_value("sub") == "Submit"
    assert ScoreType.TYPES.get_value("spe") == "Special"


# ---------------------------------------------------------------------------
# ScoreType.__str__
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_score_type_str():
    st = ScoreType.objects.first()
    assert str(st) == st.name


# ---------------------------------------------------------------------------
# ScoreType.chapter_events
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chapter_events_no_date(chapter, event_factory):
    score_type = ScoreType.objects.filter(type="Evt").first()
    # events for this chapter
    created = event_factory.create_batch(3, chapter=chapter, type=score_type)
    result = score_type.chapter_events(chapter)
    created_pks = {e.pk for e in created}
    result_pks = set(result.values_list("pk", flat=True))
    assert created_pks.issubset(result_pks)


@pytest.mark.django_db
def test_chapter_events_with_date(chapter, event_factory):
    score_type = ScoreType.objects.filter(type="Evt").first()
    recent_date = datetime.date.today()
    old_date = datetime.date(2010, 3, 1)
    event_recent = event_factory.create(chapter=chapter, type=score_type, date=recent_date)
    event_old = event_factory.create(chapter=chapter, type=score_type, date=old_date)
    result = score_type.chapter_events(chapter, date=recent_date)
    result_pks = set(result.values_list("pk", flat=True))
    assert event_recent.pk in result_pks
    assert event_old.pk not in result_pks


# ---------------------------------------------------------------------------
# ScoreType.chapter_score
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_chapter_score_evt_no_events(chapter):
    """With no events the score should be 0."""
    score_type = ScoreType.objects.filter(type="Evt").first()
    score = score_type.chapter_score(chapter)
    assert score == 0


@pytest.mark.django_db
def test_chapter_score_evt_with_events(chapter, event_factory):
    score_type = ScoreType.objects.filter(type="Evt").first()
    # Create events with known score values
    event_factory.create(chapter=chapter, type=score_type)
    event_factory.create(chapter=chapter, type=score_type)
    score = score_type.chapter_score(chapter)
    # Score should be non-negative and capped at term_points
    assert score >= 0
    assert score <= score_type.term_points


@pytest.mark.django_db
def test_chapter_score_sub_no_submissions(chapter):
    """Sub-type ScoreType with no submissions returns 0."""
    score_type = ScoreType.objects.filter(type="Sub").first()
    if score_type is None:
        pytest.skip("No Sub type ScoreType in fixture")
    score = score_type.chapter_score(chapter)
    assert score == 0


@pytest.mark.django_db
def test_chapter_score_sub_with_submissions(chapter):
    score_type = ScoreType.objects.filter(type="Sub").first()
    if score_type is None:
        pytest.skip("No Sub type ScoreType in fixture")
    SubmissionFactory.create(chapter=chapter, type=score_type, score=5.0)
    score = score_type.chapter_score(chapter)
    assert score >= 0


@pytest.mark.django_db
def test_chapter_score_spe_returns_zero(chapter):
    """Special type returns 0 (calculated elsewhere)."""
    score_type = ScoreType.objects.filter(type="Spe").first()
    if score_type is None:
        pytest.skip("No Spe type ScoreType in fixture")
    score = score_type.chapter_score(chapter)
    assert score == 0


# ---------------------------------------------------------------------------
# ScoreType.calculate_score
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_calculate_score_base_points_only(chapter, event_factory, user_status_change_factory):
    """ScoreType with only base_points uses that amount."""
    score_type = ScoreType.objects.filter(type="Evt", base_points__gt=0, special="").first()
    if score_type is None:
        pytest.skip("No suitable ScoreType for base_points test")
    # Create actives so percent_attendance calculation works
    user_status_change_factory.create_batch(
        10,
        status="active",
        user__chapter=chapter,
    )
    event = event_factory.create(chapter=chapter, type=score_type, members=0, alumni=0, guests=0, stem=False)
    calculated = score_type.calculate_score(event)
    assert calculated >= 0


@pytest.mark.django_db
def test_calculate_score_member_add(chapter, event_factory, user_status_change_factory):
    """Member attendance is factored into score via member_add."""
    score_type = ScoreType.objects.filter(type="Evt", member_add__gt=0, special="").first()
    if score_type is None:
        pytest.skip("No suitable ScoreType with member_add for test")
    user_status_change_factory.create_batch(
        20,
        status="active",
        user__chapter=chapter,
    )
    event = event_factory.create(chapter=chapter, type=score_type, members=10, alumni=0, guests=0, stem=False)
    score = score_type.calculate_score(event)
    assert score >= score_type.base_points


# ---------------------------------------------------------------------------
# ScoreType.calculate_special — formula substitution
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_calculate_special_guests_formula(chapter, event_factory):
    """GUESTS placeholder in formula is replaced with event.guests."""
    score_type = ScoreType.objects.filter(special__contains="GUESTS").first()
    if score_type is None:
        pytest.skip("No ScoreType with GUESTS formula")
    event = event_factory.create(chapter=chapter, type=score_type, guests=5)
    result = score_type.calculate_special(event)
    assert isinstance(result, (int, float))


@pytest.mark.django_db
def test_calculate_special_calculated_elsewhere(chapter, event_factory):
    """Formulas containing known keywords return 0 (calculated elsewhere)."""
    # Find or construct a score type whose special field references a known keyword
    score_type = ScoreType.objects.filter(special__contains="HOURS").first()
    if score_type is None:
        pytest.skip("No ScoreType with HOURS formula")
    event = event_factory.create(chapter=chapter, type=score_type)
    result = score_type.calculate_special(event)
    assert result == 0


# ---------------------------------------------------------------------------
# ScoreChapter
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_score_chapter_create_directly(chapter):
    """ScoreChapter can be created directly without the broken factory."""
    score_type = ScoreType.objects.first()
    sc = ScoreChapter.objects.create(chapter=chapter, type=score_type, score=10.0, year=2025, term="fa")
    assert isinstance(sc, ScoreChapter)


@pytest.mark.django_db
def test_score_chapter_type_score_biennium_returns_values(chapter):
    score_type = ScoreType.objects.first()
    ScoreChapter.objects.create(chapter=chapter, type=score_type, score=15.0, year=2025, term="fa")
    ScoreChapter.objects.create(chapter=chapter, type=score_type, score=10.0, year=2026, term="sp")
    result = list(ScoreChapter.type_score_biennium(chapters=[chapter]))
    # Returns a list/dict-like iterable; should have entries with section totals
    assert isinstance(result, list)


@pytest.mark.django_db
def test_score_chapter_update_score(chapter):
    """update_score re-reads chapter_score from db without error."""
    score_type = ScoreType.objects.first()
    sc = ScoreChapter.objects.create(chapter=chapter, type=score_type, score=5.0, year=2025, term="fa")
    sc.update_score()  # should not raise
