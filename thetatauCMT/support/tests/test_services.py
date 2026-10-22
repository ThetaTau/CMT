import datetime

import pytest
from django.utils import timezone

from core.models import CSS_ROLE
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.configs.models import Config
from thetatauCMT.support.services import (
    CSS_HOME_CHAPTER_CONFIG_KEY,
    DEFAULT_CSS_HOME_CHAPTER_SLUG,
    CSSHomeChapterError,
    css_home_chapter,
    holds_css_role,
)
from thetatauCMT.users.models import UserRoleChange
from thetatauCMT.users.tests.factories import UserFactory

from .factories import central_office, give_css_role

pytestmark = pytest.mark.django_db


def _days(n):
    return timezone.localdate() + datetime.timedelta(days=n)


def test_holds_css_role_follows_the_role_dates():
    user = UserFactory(status="css")
    give_css_role(user, start=_days(-10), end=_days(10))

    assert holds_css_role(user)
    assert holds_css_role(user, on=_days(-10))
    assert holds_css_role(user, on=_days(10))
    assert not holds_css_role(user, on=_days(-11))
    assert not holds_css_role(user, on=_days(11))
    assert holds_css_role(user, on=timezone.now())


def test_holds_css_role_is_false_for_other_roles_and_no_user():
    officer = UserFactory(status="active")
    UserRoleChange.objects.create(user=officer, role="regent", start=_days(-10), end=_days(100))

    assert not holds_css_role(officer)
    assert not holds_css_role(None)
    assert CSS_ROLE not in (officer.current_roles or [])


def test_home_chapter_defaults_to_central_office():
    home = central_office()

    assert DEFAULT_CSS_HOME_CHAPTER_SLUG == "central-office"
    assert home.slug == "central-office"
    assert css_home_chapter() == home


def test_home_chapter_can_be_configured():
    central_office()
    other = ChapterFactory(name="National Staff", greek="NS", active=False)
    Config.objects.create(key=CSS_HOME_CHAPTER_CONFIG_KEY, value="<p>national-staff</p>", description="test")

    assert css_home_chapter() == other


def test_home_chapter_must_exist():
    with pytest.raises(CSSHomeChapterError, match='No chapter has the slug "central-office"'):
        css_home_chapter()


def test_home_chapter_must_be_inactive():
    home = central_office()
    home.active = True
    home.save()

    with pytest.raises(CSSHomeChapterError, match="must be inactive"):
        css_home_chapter()
