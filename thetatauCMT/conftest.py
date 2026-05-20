import pytest
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.utils import timezone
from pytest_factoryboy import register

from thetatauCMT.ballots.tests.factories import BallotCompleteFactory, BallotFactory
from thetatauCMT.chapters.tests.factories import ChapterCurriculaFactory, ChapterFactory
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.finances.tests.factories import InvoiceFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.scores.tests.factories import ScoreChapterFactory
from thetatauCMT.submissions.tests.factories import SubmissionFactory
from thetatauCMT.tasks.tests.factories import TaskChapterFactory
from thetatauCMT.users.tests.factories import (
    UserAlterFactory,
    UserFactory,
    UserOrgParticipateFactory,
    UserRoleChangeFactory,
    UserSemesterGPAFactory,
    UserSemesterServiceHoursFactory,
    UserStatusChangeFactory,
)


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        call_command("loaddata", "scoretypes.json")
        call_command("loaddata", "tasks.json")
        from allauth.socialaccount.models import SocialApp

        current_site = Site.objects.get_current()
        # Purge duplicates accumulated from prior --reuse-db runs, then create once
        SocialApp.objects.filter(provider="google").delete()
        current_site.socialapp_set.create(
            provider="google",
            name="google",
            client_id="1234567890",
            secret="0987654321",
        )


@pytest.fixture
def test_password():
    return "strong-test-pass"


@pytest.fixture
def auto_login_user(db, client, user_factory, test_password):
    def make_auto_login(user=None, make_officer=False):
        from thetatauCMT.forms.models import RiskManagement

        if user is None:
            user = user_factory.create(password=test_password, make_officer=make_officer)
        # Create RMP record so RMPSignMiddleware does not redirect the user
        RiskManagement.objects.get_or_create(
            user=user,
            defaults=dict(
                role="regent",
                submission=None,
                date=timezone.now().date(),
                alcohol=False,
                hosting=False,
                monitoring=False,
                member=False,
                officer=False,
                abusive=False,
                hazing=False,
                substances=False,
                high_risk=False,
                transportation=False,
                property_management=False,
                guns=False,
                trademark=False,
                social=False,
                indemnification=False,
                agreement=False,
                electronic_agreement=False,
                terms_agreement=False,
                typed_name="test user",
            ),
        )
        client.force_login(user)
        return client, user

    return make_auto_login


@pytest.fixture(params=["chrome", "firefox"], scope="session")
def driver_get(request):
    from selenium import webdriver

    if request.param == "chrome":
        web_driver = webdriver.Chrome()
    if request.param == "firefox":
        web_driver = webdriver.Firefox()
    session = request.node
    for item in session.items:
        cls = item.getparent(pytest.Class)
        setattr(cls.obj, "driver", web_driver)
    yield
    web_driver.close()


register(RegionFactory)
register(ChapterFactory)
register(ChapterCurriculaFactory)
register(EventFactory)
register(BallotFactory)
register(BallotCompleteFactory)
register(InvoiceFactory)
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
