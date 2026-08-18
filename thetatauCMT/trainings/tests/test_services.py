import datetime

import pytest
from django.utils import timezone

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.forms.tests.factories import InitiationFactory
from thetatauCMT.trainings.models import COMMUNITY_EDU_COURSE_ID, COMMUNITY_EDU_COURSE_TITLE, Training
from thetatauCMT.trainings.services import chapter_completion_stats
from thetatauCMT.users.tests.factories import UserFactory


def _training(user, completed):
    return Training.objects.create(
        user=user,
        progress_id="p",
        course_id=COMMUNITY_EDU_COURSE_ID,
        course_title=COMMUNITY_EDU_COURSE_TITLE,
        completed=completed,
        max_quiz_score=100 if completed else 0,
    )


@pytest.mark.django_db
def test_chapter_completion_stats_counts_only_new_members_in_window():
    chapter = ChapterFactory.create()
    today = timezone.now().date()

    completed_user = UserFactory.create(chapter=chapter)
    InitiationFactory.create(user=completed_user, chapter=chapter, date=today - datetime.timedelta(days=30))
    _training(completed_user, completed=True)

    incomplete_user = UserFactory.create(chapter=chapter)
    InitiationFactory.create(user=incomplete_user, chapter=chapter, date=today - datetime.timedelta(days=60))
    _training(incomplete_user, completed=False)

    # Initiated well outside the default trailing-12-month window: must not count.
    old_user = UserFactory.create(chapter=chapter)
    InitiationFactory.create(user=old_user, chapter=chapter, date=today - datetime.timedelta(days=1000))
    _training(old_user, completed=True)

    stats = chapter_completion_stats(chapters=[chapter])
    assert len(stats) == 1
    stat = stats[0]
    assert stat.chapter == chapter
    assert stat.total == 2
    assert stat.completed == 1
    assert stat.percentage == 50.0
    assert stat.surcharge_bracket == "L1b"


@pytest.mark.django_db
def test_chapter_completion_stats_no_new_members_percentage_is_none():
    chapter = ChapterFactory.create()
    stats = chapter_completion_stats(chapters=[chapter])
    assert stats[0].total == 0
    assert stats[0].percentage is None
    assert stats[0].surcharge_bracket is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "completed,total,expected_bracket",
    [
        (8, 10, "none"),  # 80%
        (6, 10, "L1a"),  # 60%
        (3, 10, "L1b"),  # 30%
        (1, 10, "L1c"),  # 10%
    ],
)
def test_surcharge_bracket_matches_percentage_range(completed, total, expected_bracket):
    chapter = ChapterFactory.create()
    today = timezone.now().date()
    for i in range(total):
        user = UserFactory.create(chapter=chapter)
        InitiationFactory.create(user=user, chapter=chapter, date=today - datetime.timedelta(days=10))
        _training(user, completed=(i < completed))

    stats = chapter_completion_stats(chapters=[chapter])
    assert stats[0].surcharge_bracket == expected_bracket


@pytest.mark.django_db
def test_chapter_completion_stats_ignores_other_chapters():
    chapter = ChapterFactory.create()
    other_chapter = ChapterFactory.create()
    today = timezone.now().date()

    other_user = UserFactory.create(chapter=other_chapter)
    InitiationFactory.create(user=other_user, chapter=other_chapter, date=today - datetime.timedelta(days=10))
    _training(other_user, completed=True)

    stats = chapter_completion_stats(chapters=[chapter])
    assert stats[0].total == 0
