"""The demo seed builds each stage of the competition for local QA."""

from collections import Counter
from io import StringIO

import pytest
from django.core.management import call_command

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory
from thetatauCMT.users.models import User
from thetatauCMT.users.tests.factories import UserFactory

from .. import judging, services
from ..management.commands.seed_case_competition_demo import DEMO_EMAIL_DOMAIN, DEMO_PASSWORD, SLUG
from ..models import Competition
from .factories import member

pytestmark = pytest.mark.django_db


@pytest.fixture
def chapters(settings, tmp_path):
    """Nine chapters with members: four in one region, three in the next and two in the last."""
    settings.MEDIA_ROOT = tmp_path
    regions = [RegionFactory() for _ in range(3)]
    names = ("alpha", "beta", "chi", "delta", "epsilon", "eta", "kappa", "mu", "omega")
    result = []
    for name, region in zip(names, (0, 0, 0, 0, 1, 1, 1, 2, 2)):
        chapter = ChapterFactory(name=name, region=regions[region])
        for _ in range(3):
            member(chapter)
        result.append(chapter)
    return result


def seed(stage, **options):
    call_command("seed_case_competition_demo", stage=stage, force=True, stdout=StringIO(), **options)
    return Competition.objects.get(slug=SLUG)


def demo_judge(name):
    return f"necc-judge-{name}@{DEMO_EMAIL_DOMAIN}"


def statuses(round_):
    return Counter(services.entry_status(entry, round_) for entry in round_.entries.all())


def test_the_judging_stage_has_judges_part_way_through(chapters):
    me = UserFactory(chapter=chapters[0])

    proposal = seed("judging", judge=[me.email]).rounds.get(number=1)

    progress = {
        judge.user.email: (judge.assigned, judge.submitted, judge.drafts, judge.stepped_aside)
        for judge in judging.judge_rows(proposal)
    }
    # Casey and I are never given our own chapter's entry.
    assert progress == {
        demo_judge("avery"): (6, 5, 1, 0),
        demo_judge("blake"): (6, 3, 1, 1),
        demo_judge("casey"): (5, 0, 0, 0),
        me.email: (5, 0, 0, 0),
    }
    assert statuses(proposal) == {services.SUBMITTED: 6, services.INCOMPLETE: 1}
    assert proposal.competition.participants.count() == 8
    _, rows = judging.score_rows(proposal)
    assert [row.rank for row in rows if row.tied] == [2, 2]
    avery = User.objects.get(email=demo_judge("avery"))
    assert avery.check_password(DEMO_PASSWORD) and not avery.requires_rmp


def test_rebuilding_through_the_later_stages(chapters):
    proposal = seed("open").rounds.get(number=1)
    assert statuses(proposal) == {services.SUBMITTED: 3, services.IN_PROGRESS: 2}

    seed("results")
    proposal, final = seed("final").rounds.order_by("number")

    assert proposal.is_published and not final.is_published
    assert len(services.qualifier_chapter_ids(final)) == 4
    assert statuses(final) == {services.SUBMITTED: 3, services.INCOMPLETE: 1}
    assert sorted(final.entries.exclude(place=None).values_list("place", flat=True)) == [1, 2]
    assert User.objects.filter(username__endswith=f"@{DEMO_EMAIL_DOMAIN}").count() == 3
