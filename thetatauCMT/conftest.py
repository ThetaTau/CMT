import pytest
from pytest_factoryboy import register
from django.core.management import call_command
from ballots.tests.factories import BallotFactory, BallotCompleteFactory
from chapters.tests.factories import ChapterFactory, ChapterCurriculaFactory
from events.tests.factories import EventFactory
from finances.tests.factories import TransactionFactory
from regions.tests.factories import RegionFactory
from scores.tests.factories import ScoreChapterFactory
from submissions.tests.factories import SubmissionFactory
from tasks.tests.factories import TaskChapterFactory
from users.tests.factories import (
    UserFactory,
    UserAlterFactory,
    UserOrgParticipateFactory,
    UserSemesterGPAFactory,
    UserSemesterServiceHoursFactory,
    UserRoleChangeFactory,
    UserStatusChangeFactory,
)


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "scoretypes.json")
        call_command("loaddata", "tasks.json")


register(RegionFactory)
register(ChapterFactory)
register(ChapterCurriculaFactory)
register(EventFactory)
register(BallotFactory)
register(BallotCompleteFactory)
register(TransactionFactory)
register(ScoreChapterFactory)
register(SubmissionFactory)
register(TaskChapterFactory)
register(UserFactory)
register(UserAlterFactory)
register(UserOrgParticipateFactory)
register(UserSemesterGPAFactory)
register(UserSemesterServiceHoursFactory)
register(UserRoleChangeFactory)
register(UserStatusChangeFactory)
