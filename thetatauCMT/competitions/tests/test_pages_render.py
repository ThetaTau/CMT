"""Every page renders for a manager, before and after the results are published."""

import pytest
from django.test import override_settings
from django.urls import reverse

from thetatauCMT.chapters.tests.factories import ChapterFactory

from .. import judging, services
from .factories import (
    AssignmentFactory,
    CompetitionFactory,
    EntryFactory,
    EntryFileFactory,
    JudgeFactory,
    ParticipantFactory,
    RoundFactory,
    RubricCriterionFactory,
    SubmissionItemFactory,
    eastern,
    member,
)

pytestmark = [pytest.mark.django_db]


@override_settings(DEBUG=True)
def test_every_page_renders(auto_login_user, admin_user, freezer):
    freezer.move_to("2026-12-20 17:00:00")
    competition = CompetitionFactory(intent_opens_at=eastern(2026, 9, 1), intent_closes_at=eastern(2026, 9, 28))
    round_ = RoundFactory(competition=competition)
    SubmissionItemFactory(round=round_, label="Proposal")
    RubricCriterionFactory(round=round_, name="Impact")
    chapter = ChapterFactory(name="alpha")
    ParticipantFactory(competition=competition, chapter=chapter)
    entry = EntryFactory(round=round_, chapter=chapter, summary="S", submitted_at=eastern(2026, 12, 8))
    entry_file = EntryFileFactory(entry=entry, item=round_.items.get())
    judge = JudgeFactory(round=round_, user=member(ChapterFactory(name="beta"), status="alumni"))
    assignment = AssignmentFactory(judge=judge, entry=entry)
    client, _ = auto_login_user(user=admin_user)
    slug = competition.slug
    urls = [
        reverse("competitions:list"),
        reverse("competitions:detail", args=[slug]),
        reverse("competitions:manage", args=[slug]),
        reverse("competitions:submit_on_behalf", args=[slug, 1, chapter.slug]),
        reverse("competitions:extension", args=[slug, 1, chapter.slug]),
        reverse("competitions:entry", args=[entry.public_id]),
        reverse("competitions:judges", args=[slug, 1]),
        reverse("competitions:scores", args=[slug, 1]),
        reverse("competitions:scorecard", args=[assignment.public_id]),
        reverse("competitions:export", args=[slug, "participants"]),
        reverse("competitions:export", args=[slug, "entries"]),
        reverse("competitions:export", args=[slug, "scores"]),
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, (url, response.status_code)
    assert client.get(reverse("competitions:file", args=[entry_file.public_id])).status_code == 302
    judging.save_scorecard(assignment, {round_.criteria.get().pk: (4, "Good")}, "Nice work", submit=True)
    entry.advanced = True
    entry.save()
    judging.publish_results(round_, admin_user)
    for url in [reverse("competitions:results", args=[slug, 1]), reverse("competitions:scores", args=[slug, 1])]:
        assert client.get(url).status_code == 200, url
    judge_client, _ = auto_login_user(user=judge.user)
    assert judge_client.get(reverse("competitions:judging")).status_code == 200
    home = judge_client.get(reverse("home"))
    assert home.status_code == 200
    assert services.can_view_entry(judge.user, entry)
