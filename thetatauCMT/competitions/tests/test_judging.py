"""NECCWI-9 to 13: judges, scorecards, scores, selection, results and the final round."""

from decimal import Decimal

import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from thetatauCMT.awards.models import AwardGrant
from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.regions.tests.factories import RegionFactory

from .. import judging, reminders, services
from ..models import Assignment, NotificationLog, Round
from .factories import (
    EntryFactory,
    EntryFileFactory,
    JudgeFactory,
    ParticipantFactory,
    RoundFactory,
    RubricCriterionFactory,
    SubmissionItemFactory,
    eastern,
    give_role,
    member,
    national_officer,
)

pytestmark = pytest.mark.django_db
Kind = NotificationLog.Kind
JUDGING = eastern(2026, 12, 14, 9)
PUBLISHED = eastern(2027, 1, 20, 12)


@pytest.fixture
def manager():
    return give_role(member(ChapterFactory(name="kappa"), status="alumni"), "professional development director")


@pytest.fixture
def round_():
    round_ = RoundFactory()
    SubmissionItemFactory(round=round_, label="Proposal")
    RubricCriterionFactory(round=round_, name="Impact", order=1)
    RubricCriterionFactory(round=round_, name="Feasibility", order=2)
    return round_


@pytest.fixture
def east():
    return RegionFactory(name="East", slug="east")


@pytest.fixture
def west():
    return RegionFactory(name="West", slug="west")


def chapter_in(name, region):
    chapter = ChapterFactory(name=name)
    chapter.region = region
    chapter.save()
    return chapter


def submitted(round_, chapter, **kwargs):
    ParticipantFactory(competition=round_.competition, chapter=chapter)
    entry = EntryFactory(round=round_, chapter=chapter, summary="S", submitted_at=eastern(2026, 12, 8), **kwargs)
    EntryFileFactory(entry=entry, item=round_.items.get())
    return entry


def judge_of(round_, chapter_name="omega", **kwargs):
    return JudgeFactory(round=round_, user=member(ChapterFactory(name=chapter_name), status="alumni", **kwargs))


def score(assignment, points, feedback="Good work", submit=True, comments=("", "")):
    criteria = list(assignment.judge.round.criteria.all())
    scores = {criterion.pk: (value, comment) for criterion, value, comment in zip(criteria, points, comments)}
    return judging.save_scorecard(assignment, scores, feedback, submit=submit, now=JUDGING)


def assignment_for(judge, entry):
    return Assignment.objects.get(judge=judge, entry=entry)


class TestAssignments:
    def test_every_judge_every_entry_but_their_own_chapter(self, round_, east):
        alpha, beta = chapter_in("alpha", east), chapter_in("beta", east)
        entry_a, entry_b = submitted(round_, alpha), submitted(round_, beta)
        outside = judge_of(round_)
        insider = JudgeFactory(round=round_, user=member(alpha, status="alumni"))
        assert judging.sync_assignments(round_, eastern(2026, 12, 11, 12)) == 0  # not closed yet
        assert judging.sync_assignments(round_, JUDGING) == 3
        assert set(Assignment.objects.values_list("judge_id", "entry_id")) == {
            (outside.pk, entry_a.pk),
            (outside.pk, entry_b.pk),
            (insider.pk, entry_b.pk),
        }
        assert judging.sync_assignments(round_, JUDGING) == 0

    def test_late_withdrawn_and_ineligible_entries(self, round_, east):
        judge = judge_of(round_)
        late = submitted(round_, chapter_in("alpha", east), deadline_override=eastern(2026, 12, 15, 23, 59))
        gone = submitted(round_, chapter_in("beta", east))
        gone.chapter.competition_participations.update(withdrawn_at=JUDGING)
        submitted(round_, chapter_in("delta", east), eligible=False)
        assert judging.sync_assignments(round_, JUDGING) == 0
        assert judging.sync_assignments(round_, eastern(2026, 12, 16, 9)) == 1
        assert Assignment.objects.get().entry == late
        assert judge.assignments.count() == 1

    def test_judges_page_for_managers(self, round_, auto_login_user):
        manager = give_role(member(ChapterFactory(name="delta"), status="alumni"), "professional development director")
        newcomer = member(ChapterFactory(name="beta"), status="alumni")
        url = reverse("competitions:judges", args=[round_.competition.slug, 1])
        with override_settings(DEBUG=True):
            client, _ = auto_login_user(user=member(ChapterFactory(name="alpha")))
            assert client.get(url).status_code == 302
            client, _ = auto_login_user(user=manager)
            client.post(url, {"action": "add", "user": newcomer.pk})
            judge = round_.judges.get()
            assert judge.user == newcomer and judge.added_by == manager
            client.post(url, {"action": "remove", "judge": judge.pk})
            judge.refresh_from_db()
            assert judge.removed_at is not None


class TestJudgeEmails:
    def test_judging_open_once_and_the_due_ladder(self, round_, east):
        submitted(round_, chapter_in("alpha", east))
        busy, done = judge_of(round_, "beta"), judge_of(round_, "delta")
        reminders.send_scheduled(now=eastern(2026, 12, 12, 9))
        assert NotificationLog.objects.filter(kind=Kind.JUDGING_OPEN).count() == 2
        reminders.send_scheduled(now=eastern(2026, 12, 13, 9))
        assert NotificationLog.objects.filter(kind=Kind.JUDGING_OPEN).count() == 2
        score(assignment_for(done, round_.entries.get()), [4, 4])
        reminders.send_scheduled(now=eastern(2027, 1, 1, 9))  # 7 days before the January 8 deadline
        reminders.send_scheduled(now=eastern(2027, 1, 1, 15))
        due = NotificationLog.objects.filter(kind=Kind.JUDGING_DUE)
        assert [(log.user, log.key.split(":")[-2]) for log in due] == [(busy.user, "7")]
        reminders.send_scheduled(now=eastern(2027, 1, 7, 9))
        assert NotificationLog.objects.filter(kind=Kind.JUDGING_DUE).count() == 2
        subjects = [message.subject for message in mail.outbox if "scorecards due" in message.subject]
        assert subjects[-1] == "NECC: Proposal scorecards due tomorrow: 1 still to do"

    def test_a_judge_added_late_gets_judging_open_then_the_ladder(self, round_, east):
        submitted(round_, chapter_in("alpha", east))
        reminders.send_scheduled(now=eastern(2026, 12, 12, 9))
        late = judge_of(round_)
        reminders.send_scheduled(now=eastern(2027, 1, 7, 9))
        logs = list(NotificationLog.objects.filter(user=late.user).values_list("kind", flat=True))
        assert logs == [Kind.JUDGING_OPEN]


class TestScorecards:
    @pytest.fixture
    def assignment(self, round_, east):
        submitted(round_, chapter_in("alpha", east))
        judge_of(round_)
        judging.sync_assignments(round_, JUDGING)
        return Assignment.objects.get()

    def test_drafts_can_be_partial_and_submitting_needs_everything(self, assignment):
        draft = score(assignment, [4, None], feedback="", submit=False)
        assert draft.submitted_at is None and draft.total is None
        with pytest.raises(services.CompetitionError, match="Still to score: Feasibility"):
            score(assignment, [4, None])
        with pytest.raises(services.CompetitionError, match="overall feedback"):
            score(assignment, [4, 5], feedback="  ")
        with pytest.raises(services.CompetitionError, match="between 1 and 5"):
            score(assignment, [4, 6])
        card = score(assignment, [4, 5])
        assert card.submitted_at == JUDGING and card.total == 9
        card = score(assignment, [2, 5], submit=False)  # a submitted card stays submitted
        assert card.submitted_at is not None and card.total == 7

    def test_the_rubric_locks_on_the_first_save(self, assignment, round_):
        assert round_.rubric_locked_at is None
        score(assignment, [None, None], feedback="", submit=False)
        round_.refresh_from_db()
        assert round_.rubric_locked_at == JUDGING

    def test_only_the_assigned_judge_opens_it(self, assignment, auto_login_user, freezer):
        url = reverse("competitions:scorecard", args=[assignment.public_id])
        freezer.move_to(JUDGING)
        other_judge = judge_of(assignment.judge.round, "beta")
        with override_settings(DEBUG=True):
            client, _ = auto_login_user(user=other_judge.user)
            assert client.get(url).status_code == 404
            client, _ = auto_login_user(user=assignment.judge.user)
            assert client.get(url).status_code == 200
            criteria = list(assignment.judge.round.criteria.all())
            data = {"action": "submit", "feedback": "Clear and bold"}
            data.update({f"points_{criterion.pk}": "5" for criterion in criteria})
            client.post(url, data)
        assignment.scorecard.refresh_from_db()
        assert assignment.scorecard.total == 10

    def test_read_only_once_published(self, assignment, round_):
        score(assignment, [4, 4])
        round_.results_published_at = PUBLISHED
        round_.save()
        assignment = Assignment.objects.select_related("judge__round").get(pk=assignment.pk)
        assert not judging.can_score(assignment.judge.user, assignment, PUBLISHED)

    def test_stepping_aside(self, assignment):
        with pytest.raises(services.CompetitionError):
            judging.step_aside(assignment, " ")
        judging.step_aside(assignment, "My cousin is on the team", now=JUDGING)
        assert judging.assignment_status(assignment) == judging.STEPPED_ASIDE
        assert not judging.can_score(assignment.judge.user, assignment, JUDGING)


class TestScoresAndSelection:
    @pytest.fixture
    def setup(self, round_, east, west):
        round_.advance_per_region = 2
        round_.advance_total = 3
        round_.save()
        entries = {
            name: submitted(round_, chapter_in(name, region))
            for name, region in [("alpha", east), ("beta", east), ("delta", east), ("epsilon", west), ("zeta", west)]
        }
        judges = [judge_of(round_, "omega"), judge_of(round_, "sigma")]
        judging.sync_assignments(round_, JUDGING)
        return entries, judges

    def give(self, judge, entry, points, submit=True):
        return score(assignment_for(judge, entry), points, submit=submit)

    def test_averages_ranks_ties_and_what_counts(self, round_, setup):
        entries, (first, second) = setup
        self.give(first, entries["alpha"], [5, 5])
        self.give(second, entries["alpha"], [4, 4])
        self.give(first, entries["beta"], [4, 5])
        self.give(second, entries["beta"], [4, 4])
        self.give(first, entries["delta"], [5, 4])
        self.give(second, entries["delta"], [1, 1], submit=False)  # a draft counts for nothing
        judging.step_aside(assignment_for(second, entries["epsilon"]), "Conflict", now=JUDGING)
        self.give(first, entries["epsilon"], [3, 3])
        criteria, rows = judging.score_rows(round_)
        by_name = {row.entry.chapter.name: row for row in rows}
        assert by_name["alpha"].average == Decimal("9.00")
        assert by_name["alpha"].criterion_averages == [Decimal("4.50"), Decimal("4.50")]
        assert by_name["alpha"].spread == 2
        assert (by_name["beta"].average, by_name["delta"].average) == (Decimal("8.50"), Decimal("9.00"))
        assert (by_name["delta"].missing, by_name["epsilon"].expected) == (1, 1)
        assert [(by_name[name].rank, by_name[name].tied) for name in ("alpha", "delta", "beta")] == [
            (1, True),
            (1, True),
            (3, False),
        ]
        assert by_name["zeta"].average is None and by_name["zeta"].rank is None

    def test_preselection_keeps_to_the_limits_and_the_minimum(self, round_, setup, auto_login_user, manager):
        entries, (first, _) = setup
        for name, points in [
            ("alpha", [5, 5]),
            ("beta", [4, 4]),
            ("delta", [3, 3]),
            ("epsilon", [5, 4]),
            ("zeta", [2, 1]),
        ]:
            self.give(first, entries[name], points)
        result = judging.preselect(round_)
        chosen = {entry.chapter.name for entry in round_.entries.filter(pk__in=result.selected)}
        assert chosen == {"alpha", "beta", "epsilon", "zeta"}
        assert any("the most is 3" in warning for warning in result.warnings)
        with override_settings(DEBUG=True):
            client, _ = auto_login_user(user=manager)
            page = client.get(reverse("competitions:scores", args=[round_.competition.slug, 1])).content.decode()
        assert "The pre-selection has 4 entries; the most is 3." in page  # before anyone presses Pre-select
        round_.min_average_to_advance = Decimal("5")
        round_.save()
        result = judging.preselect(round_)
        assert {entry.chapter.name for entry in round_.entries.filter(pk__in=result.selected)} == {
            "alpha",
            "beta",
            "epsilon",
        }

    def test_the_scores_page_is_for_managers(self, round_, setup, auto_login_user, manager):
        entries, (first, second) = setup
        self.give(first, entries["alpha"], [5, 3])
        self.give(second, entries["alpha"], [4, 4])
        url = reverse("competitions:scores", args=[round_.competition.slug, 1])
        with override_settings(DEBUG=True):
            client, _ = auto_login_user(user=national_officer())
            assert client.get(url).status_code == 302
            client, _ = auto_login_user(user=manager)
            page = client.get(url).content.decode()
            # The decision stays in the entry's row; each criterion's average opens in the row under it.
            alpha = entries["alpha"].pk
            row, details = page.index(f'id="entry-{alpha}"'), page.index(f'id="scores-{alpha}"')
            assert row < page.index('name="advanced"', row) < details
            assert "Impact</div>" in page[details:] and "4.50" in page[details:]
            client.post(url, {"action": "preselect"})
        assert round_.entries.filter(advanced__isnull=True).count() == 0


class TestPublishing:
    @pytest.fixture
    def published_setup(self, round_, east):
        qualifier = submitted(round_, chapter_in("alpha", east))
        other = submitted(round_, chapter_in("beta", east))
        judge = judge_of(round_)
        judging.sync_assignments(round_, JUDGING)
        score(assignment_for(judge, qualifier), [5, 5], comments=("Strong impact", "Unkind remark"))
        score(assignment_for(judge, other), [2, 2])
        return qualifier, other, judge

    def test_publishing_needs_a_decision_on_every_eligible_entry(self, round_, published_setup):
        qualifier, other, _ = published_setup
        with pytest.raises(services.CompetitionError, match="Decide every eligible entry"):
            judging.publish_results(round_, None, now=PUBLISHED)
        judging.set_decision(qualifier, True, None)
        judging.set_eligibility(other, False, "Over the slide limit", None)
        assert judging.publish_blockers(round_) == []

    def test_results_feedback_emails_and_awards_once(
        self, round_, published_setup, manager, django_capture_on_commit_callbacks
    ):
        qualifier, other, judge = published_setup
        judging.set_decision(qualifier, True, None)
        judging.set_decision(other, False, None)
        hidden = qualifier.assignments.get().scorecard.scores.get(criterion__name="Feasibility")
        judging.set_hidden(hidden, True)
        reader = member(other.chapter)
        assert not services.can_view_entry(reader, qualifier, PUBLISHED)
        with django_capture_on_commit_callbacks(execute=True):
            assert judging.publish_results(round_, manager, now=PUBLISHED)
        round_.refresh_from_db()
        assert services.can_view_entry(reader, qualifier, PUBLISHED)
        assert not services.can_view_entry(member(qualifier.chapter), other, PUBLISHED)
        assert judging.result_label(qualifier) == "Regional Qualifier"
        assert judging.result_label(other) == "Not selected"
        feedback = judging.chapter_feedback(qualifier)
        assert [(row.label, row.feedback, row.comments) for row in feedback] == [
            ("Judge 1", "Good work", [("Impact", "Strong impact")])
        ]
        assert judge.user.name not in str(feedback)
        results = NotificationLog.objects.filter(kind=Kind.RESULTS)
        assert results.count() == 2
        assert (
            AwardGrant.objects.filter(
                recipient_chapter=qualifier.chapter, award_type__name="NECC Regional Qualifier"
            ).count()
            == 1
        )
        with django_capture_on_commit_callbacks(execute=True):
            assert not judging.publish_results(round_, manager, now=PUBLISHED)
        assert results.count() == 2 and AwardGrant.objects.count() == 1
        # Unpublishing (Django admin) hides results; publishing again sends and grants nothing new.
        round_.results_published_at = None
        round_.save()
        assert not services.can_view_entry(reader, qualifier, PUBLISHED)
        with django_capture_on_commit_callbacks(execute=True):
            assert judging.publish_results(round_, manager, now=PUBLISHED)
        assert results.count() == 2 and AwardGrant.objects.count() == 1
        assert not judging.can_score(judge.user, qualifier.assignments.get(), PUBLISHED)

    def test_the_results_page_after_publishing(self, round_, published_setup, auto_login_user, freezer, manager):
        qualifier, other, _ = published_setup
        judging.set_decision(qualifier, True, None)
        judging.set_decision(other, False, None)
        url = reverse("competitions:results", args=[round_.competition.slug, 1])
        freezer.move_to(PUBLISHED)
        with override_settings(DEBUG=True):
            client, _ = auto_login_user(user=member(ChapterFactory(name="delta")))
            assert client.get(url).status_code == 302
            judging.publish_results(round_, manager)
            page = client.get(url).content.decode()
        assert qualifier.title in page and other.title not in page


class TestFinalRound:
    @pytest.fixture
    def final(self, round_, east):
        round_.save()
        qualifier = submitted(round_, chapter_in("alpha", east), advanced=True)
        submitted(round_, chapter_in("beta", east), advanced=False)
        round_.results_published_at = PUBLISHED
        round_.save()
        final = RoundFactory(
            competition=round_.competition,
            number=2,
            name="Final submission",
            eligibility=Round.Eligibility.ADVANCED,
            selection=Round.Selection.PLACES,
            places=2,
            opens_at=eastern(2027, 5, 21),
            closes_at=eastern(2027, 5, 28, 23, 59, 59),
            judging_closes_at=eastern(2027, 6, 25, 23, 59, 59),
        )
        SubmissionItemFactory(round=final, label="Final report")
        RubricCriterionFactory(round=final, name="Results")
        return final, qualifier.chapter

    def test_only_qualifiers_submit(self, final):
        final_round, qualifier = final
        during = eastern(2027, 5, 25)
        assert services.can_submit(member(qualifier), final_round, qualifier, during)
        beta = ChapterFactory(name="beta")
        assert not services.can_submit(member(beta), final_round, beta, during)

    def test_places_stay_hidden_until_the_winners_are_announced(
        self, final, manager, django_capture_on_commit_callbacks, auto_login_user
    ):
        final_round, qualifier = final
        entry = EntryFactory(round=final_round, chapter=qualifier, summary="S", submitted_at=eastern(2027, 5, 27))
        EntryFileFactory(entry=entry, item=final_round.items.get())
        judge = JudgeFactory(round=final_round, user=member(ChapterFactory(name="omega"), status="alumni"))
        judging.sync_assignments(final_round, eastern(2027, 6, 1))
        judging.set_place(entry, 1, None)
        with override_settings(DEBUG=True):
            client, _ = auto_login_user(user=manager)
            page = client.get(reverse("competitions:scores", args=[final_round.competition.slug, 2])).content.decode()
        assert '<option value="1" selected>1st</option>' in page
        with pytest.raises(services.CompetitionError, match="2nd place still open"):
            judging.publish_results(final_round, None)
        assert judging.result_label(entry) is None
        assert not services.can_view_entry(national_officer(), entry, eastern(2027, 6, 1))
        final_round.places = 1
        final_round.save()
        with django_capture_on_commit_callbacks(execute=True):
            assert judging.publish_results(final_round, manager, now=eastern(2027, 7, 17, 20))
            assert not judging.publish_results(final_round, manager, now=eastern(2027, 7, 17, 21))
        entry.refresh_from_db()
        assert judging.result_label(entry) == "1st place"
        assert services.can_view_entry(national_officer(), entry, eastern(2027, 7, 18))
        assert NotificationLog.objects.filter(kind=Kind.WINNERS).count() == 1
        assert AwardGrant.objects.filter(award_type__name="NECC First Place", recipient_chapter=qualifier).count() == 1
        assert judge.assignments.count() == 1


def test_publishing_makes_a_missing_award_type(round_, east, manager):
    from thetatauCMT.awards.models import AwardType

    # A fresh database: migration 0002 skipped them, so `loaddata award_types` could not overwrite them.
    AwardType.objects.filter(name__startswith="NECC").delete()
    entry = submitted(round_, chapter_in("alpha", east), advanced=True)
    grants = judging.grant_awards(round_, manager, PUBLISHED)
    award_type = AwardType.objects.get(name="NECC Regional Qualifier")
    assert [grant.recipient_chapter for grant in grants] == [entry.chapter]
    assert (award_type.level, award_type.category, award_type.allow_multiple_winners) == (
        "chapter",
        "Case Competition",
        True,
    )


def test_awards_follow_the_feature_flag(round_, east):
    from .factories import set_config

    set_config("FEATURE_AWARDS", "off")
    entry = submitted(round_, chapter_in("alpha", east), advanced=True)
    assert entry.advanced
    assert judging.grant_awards(round_, None, PUBLISHED) == []
    assert not AwardGrant.objects.exists()


def test_my_judging_lists_assignments_and_turns_others_away(round_, east, auto_login_user, freezer):
    submitted(round_, chapter_in("alpha", east))
    judge = judge_of(round_)
    judging.sync_assignments(round_, JUDGING)
    freezer.move_to(JUDGING)
    with override_settings(DEBUG=True):
        client, _ = auto_login_user(user=judge.user)
        page = client.get(reverse("competitions:judging")).content.decode()
        assert "Score it" in page
        client, _ = auto_login_user(user=member(ChapterFactory(name="delta")))
        assert client.get(reverse("competitions:judging")).status_code == 302


class TestFindingTheScorecards:
    """A judge sees what is left to score on every page (owner, 2026-11-21)."""

    def test_drafts_count_as_to_do_and_submitted_or_stepped_aside_do_not(self, round_, east):
        entries = [submitted(round_, chapter_in(name, east)) for name in ("alpha", "beta", "delta", "epsilon")]
        judge = judge_of(round_)
        judging.sync_assignments(round_, JUDGING)
        score(assignment_for(judge, entries[1]), [4, 4], submit=False)
        score(assignment_for(judge, entries[2]), [4, 4])
        judging.step_aside(assignment_for(judge, entries[3]), "Conflict", now=JUDGING)
        to_do = judging.scorecards_to_do(judge.user)
        assert to_do.count == 2
        assert [(row.round, row.deadline) for row in to_do.rounds] == [(round_, "Fri, Jan 8, 2027, 11:59 pm Eastern")]
        round_.competition.is_published = False
        round_.competition.save()
        assert not judging.scorecards_to_do(judge.user) and not judging.judges_anything(judge.user)

    def test_members_who_do_not_judge_pay_one_query_for_the_menu(self, rf, django_assert_num_queries):
        from ..context_processors import case_competition

        request = rf.get("/")
        request.user = member(ChapterFactory(name="delta"))
        context = case_competition(request)
        with django_assert_num_queries(1):
            assert not context["case_competition_to_do"] and not context["case_competition_judging"]

    def test_the_bubble_the_home_nudge_and_the_pages_lead_to_the_scorecards(
        self, round_, east, auto_login_user, freezer, manager
    ):
        entry = submitted(round_, chapter_in("alpha", east))
        other = submitted(round_, chapter_in("beta", east))
        judge = judge_of(round_)
        detail = reverse("competitions:detail", args=[round_.competition.slug])
        with override_settings(DEBUG=True):
            freezer.move_to("2026-12-08 17:00:00")
            client, _ = auto_login_user(user=judge.user)
            page = client.get(detail).content.decode()
            assert "Judging starts when its window closes, Fri, Dec 11, 2026, 11:59 pm Eastern." in page
            assert 'id="judging-to-do"' not in page

            judging.sync_assignments(round_, JUDGING)
            freezer.move_to(JUDGING)
            client, _ = auto_login_user(user=judge.user)
            home = client.get(reverse("home")).content.decode()
            assert 'id="judging-to-do"' in home and "2 Case Competition scorecards to submit" in home
            assert home.index('id="judging-nudge"') < home.index("<h1>Announcements</h1>")
            assert "2 of 2 scorecards still to submit" in client.get(detail).content.decode()
            mine = assignment_for(judge, entry)
            entry_url = reverse("competitions:entry", args=[entry.public_id])
            page = client.get(entry_url).content.decode()
            assert reverse("competitions:scorecard", args=[mine.public_id]) in page and "Score this entry" in page
            score(mine, [4, 4], submit=False)
            assert "Finish your scorecard" in client.get(entry_url).content.decode()
            managers_view, _ = auto_login_user(user=manager)
            page = managers_view.get(entry_url).content.decode()
            assert "Your scorecard" not in page and "You are judging this entry" not in page
            client, _ = auto_login_user(user=judge.user)  # one shared test client: sign the judge back in

            score(mine, [4, 4])
            score(assignment_for(judge, other), [3, 3])
            home = client.get(reverse("home")).content.decode()
            assert 'id="judging-to-do"' not in home and 'id="judging-nudge"' not in home
            assert reverse("competitions:judging") in home  # still in the menus until the results are out
            assert "Nothing left to score" in client.get(detail).content.decode()

            round_.results_published_at = PUBLISHED
            round_.save()
            assert reverse("competitions:judging") not in client.get(reverse("home")).content.decode()
