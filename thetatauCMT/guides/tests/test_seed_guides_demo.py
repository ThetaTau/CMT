"""``seed_guides_demo`` (TWI-11).

A QA seed is only useful if it can be re-run, and only safe if it cannot fire in
production by accident. Both are tested here; what it *renders* is covered by
the manual script in docs/specs/guides-qa.md.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from thetatauCMT.announcements.models import Announcement
from thetatauCMT.guides.models import Feature
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _seed(**kwargs):
    call_command("seed_guides_demo", verbosity=0, **kwargs)


def test_refuses_to_run_outside_debug_without_force(settings):
    settings.DEBUG = False
    with pytest.raises(CommandError):
        call_command("seed_guides_demo", verbosity=0)


def test_runs_in_debug_without_force(settings):
    settings.DEBUG = True
    _seed()
    assert Announcement.objects.filter(title__startswith="[DEMO] ").exists()


def test_is_idempotent():
    UserFactory.create_batch(3)
    _seed(force=True)
    first = Announcement.objects.filter(title__startswith="[DEMO] ").count()

    _seed(force=True)

    assert Announcement.objects.filter(title__startswith="[DEMO] ").count() == first


def test_seeds_a_feature_released_today_so_whats_new_has_something():
    from django.utils import timezone

    _seed(force=True)
    feature = Feature.objects.get(key="demo-brand-new-thing")
    assert feature.released_at == timezone.now().date()


def test_flush_removes_only_demo_rows():
    real = Announcement.objects.create(title="A real announcement", content="<p>Keep me.</p>")
    _seed(force=True)

    _seed(force=True, flush=True)

    assert Announcement.objects.filter(pk=real.pk).exists()
    assert Announcement.objects.filter(title__startswith="[DEMO] ").count() == 4
