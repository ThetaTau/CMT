from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def chapter():
    chapter = ChapterFactory(name="alpha")
    for badge in range(1, 13):
        UserFactory(chapter=chapter, badge_number=badge, current_status="alumni" if badge < 6 else "active")
    UserFactory(chapter=chapter, badge_number=2_000_001, current_status="pnm")
    return chapter


def _seed(*args):
    out = StringIO()
    call_command("seed_big_little_demo", *args, stdout=out)
    return out.getvalue()


def test_refuses_outside_debug_without_force(chapter, settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match="Refusing to seed"):
        _seed("--chapter", chapter.slug)


def test_builds_several_families_with_twins_and_one_changed_big(chapter):
    output = _seed("--chapter", chapter.slug, "--force")

    assert output.strip() == "Recorded 9 pairing(s) and changed 1 Big(s) for alpha."
    current = BigLittle.objects.current().filter(chapter=chapter)
    assert current.count() == 9
    assert not current.filter(little__current_status="pnm").exists()
    littles_per_big = [services.current_little_links(link.big).count() for link in current]
    assert 2 in littles_per_big
    assert BigLittle.objects.former().filter(chapter=chapter).count() == 1
    roots = {link.big_id for link in current} - {link.little_id for link in current}
    assert len(roots) == 3


def test_running_again_changes_nothing_and_reset_starts_over(chapter):
    _seed("--chapter", chapter.slug, "--force")

    assert _seed("--chapter", chapter.slug, "--force").strip() == (
        "Recorded 0 pairing(s) and changed 0 Big(s) for alpha."
    )
    assert BigLittle.objects.count() == 10

    _seed("--chapter", chapter.slug, "--force", "--reset")
    assert BigLittle.objects.count() == 10


def test_unknown_chapter_and_too_few_members():
    with pytest.raises(CommandError, match="No chapter"):
        _seed("--chapter", "nowhere", "--force")
    lonely = ChapterFactory(name="beta")
    UserFactory(chapter=lonely, current_status="active")
    with pytest.raises(CommandError, match="at least two initiated members"):
        _seed("--chapter", lonely.slug, "--force")
