import pytest
from pytest_factoryboy import register
from django.core.management import call_command
from chapters.tests.factories import ChapterFactory, ChapterCurriculaFactory
from regions.tests.factories import RegionFactory
from events.tests.factories import EventFactory


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "scoretypes.json")
        call_command("loaddata", "tasks.json")


register(RegionFactory)
register(ChapterFactory)
register(ChapterCurriculaFactory)
register(EventFactory)
