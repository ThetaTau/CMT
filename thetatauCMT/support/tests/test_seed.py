"""CSSWI-9: the demo seed command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from thetatauCMT.chapters.models import Chapter
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.support.management.commands.seed_css_demo import DEMO_EMAIL, DEMO_PASSWORD
from thetatauCMT.support.services import remove_css
from thetatauCMT.users.models import User

pytestmark = pytest.mark.django_db


@override_settings(DEBUG=True)
def test_the_demo_seed_works_on_a_fresh_database_and_is_safe_to_rerun():
    region = RegionFactory()
    for name in ("alpha", "beta", "delta", "epsilon", "zeta"):
        ChapterFactory(name=name, region=region)

    call_command("seed_css_demo", stdout=StringIO())

    css = User.objects.get(email=DEMO_EMAIL)
    assert css.current_status == "css" and css.check_password(DEMO_PASSWORD)
    assert css.chapter.slug == "central-office" and not css.chapter.active
    assert sorted(css.support_assignments.current().values_list("chapter__name", flat=True)) == [
        "alpha",
        "beta",
        "delta",
    ]
    assert list(css.support_assignments.ended().values_list("chapter__name", flat=True)) == ["epsilon"]

    remove_css(css)
    call_command("seed_css_demo", stdout=StringIO())

    css = User.objects.get(email=DEMO_EMAIL)
    assert css.is_active and css.support_assignments.current().count() == 3
    assert User.objects.filter(email=DEMO_EMAIL).count() == 1
    assert Chapter.objects.filter(slug="central-office").count() == 1


def test_the_demo_seed_refuses_outside_debug():
    with pytest.raises(CommandError):
        call_command("seed_css_demo", stdout=StringIO())
