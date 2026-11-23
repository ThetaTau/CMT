"""Judging, scores, selection and results (NECCWI-9 to 13).

Every judge of a round scores every complete entry except their own chapter's (Q17 A), on a
scorecard per assignment. An entry's score is the average of its counted scorecards' totals
(Q18 A, S16): submitted ones, from judges still on the round, not stepped aside. Managers
pre-select the top entries in each region (Q20 A), change any decision, and publish. The
final round awards places, and publishing it is announcing the winners at Convention (Q23 A).
"""

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, F, Q

from . import services
from .models import Assignment, CriterionScore, Entry, Judge, NotificationLog, Round, Scorecard
from .services import CompetitionError

logger = logging.getLogger(__name__)
Kind = NotificationLog.Kind
# The "National" region holds no geographic chapters, so per-region limits ignore it (Codebase facts 13).
NATIONAL_REGION_SLUG = "national"
QUALIFIER_AWARD = "NECC Regional Qualifier"
PLACE_AWARDS = {1: "NECC First Place", 2: "NECC Second Place"}
# The Q24 award types, as migration competitions 0002 makes them; award_type_for makes any missing.
AWARD_TYPE_DEFAULTS = {
    QUALIFIER_AWARD: {
        "description": "A chapter whose proposal was selected as a Regional Qualifier in the National Engineering "
        "Case Competition, advancing to the funded final round.",
        "eligibility": "Chapters whose proposal judges and the competition managers selected, up to two per region.",
        "single_winner": False,
        "allow_multiple_winners": True,
    },
    "NECC First Place": {
        "description": "The chapter that won first place in the National Engineering Case Competition.",
        "eligibility": "Regional Qualifiers that made a final submission. Announced at Convention.",
        "single_winner": True,
    },
    "NECC Second Place": {
        "description": "The chapter that won second place in the National Engineering Case Competition.",
        "eligibility": "Regional Qualifiers that made a final submission. Announced at Convention.",
        "single_winner": True,
    },
}

NOT_STARTED, DRAFT, SUBMITTED, STEPPED_ASIDE = "not_started", "draft", "submitted", "stepped_aside"
SCORECARD_LABELS = {NOT_STARTED: "Not started", DRAFT: "Draft", SUBMITTED: "Submitted", STEPPED_ASIDE: "Stepped aside"}


def ordinal(number):
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _plural(count, one, many):
    return f"{count} {one if count == 1 else many}"


# --- Judges and assignments (NECCWI-9) ---------------------------------------------------


def active_judges(round_):
    return round_.judges.active().select_related("user", "user__chapter").order_by("user__name")


def is_judge(user, round_):
    return services.is_signed_in(user) and round_.judges.active().filter(user=user).exists()


def judges_anything(user):
    """Judging a round whose results are not published yet: the "My Judging" menu links (S24).

    Only published competitions count, as on My Judging itself.
    """
    if not services.is_signed_in(user):
        return False
    return (
        Judge.objects.active()
        .filter(user=user, round__results_published_at__isnull=True, round__competition__is_published=True)
        .exists()
    )


@transaction.atomic
def add_judge(round_, user, by=None, now=None):
    """Add anyone with a CMT account as a judge (Q16 A); adding a removed judge restores them.

    Returns ``(judge, added)``. When judging has started, their assignments are made at once.
    """
    if round_.is_published:
        raise CompetitionError("The results are published, so judges can no longer be added.")
    judge, created = Judge.objects.get_or_create(round=round_, user=user, defaults={"added_by": by})
    restored = False
    if not created and judge.removed_at is not None:
        judge.removed_at = None
        judge.save(update_fields=["removed_at", "modified"])
        restored = True
    if created or restored:
        sync_assignments(round_, now)
    return judge, created or restored


def remove_judge(judge, now=None):
    """Removing a judge deletes nothing, but their scorecards stop counting (S16)."""
    if judge.removed_at is not None:
        return False
    judge.removed_at = services._now(now)
    judge.save(update_fields=["removed_at", "modified"])
    return True


def entries_for_judging(round_, now=None):
    """Complete, eligible entries of chapters still taking part, once their window has fully closed (S14)."""
    withdrawn = services.withdrawn_chapter_ids(round_.competition)
    entries = services.entries_with_files(
        round_.entries.filter(eligible=True, submitted_at__isnull=False).exclude(chapter_id__in=withdrawn)
    )
    return [
        entry for entry in entries if services.judging_started(round_, entry, now) and services.entry_is_complete(entry)
    ]


@transaction.atomic
def sync_assignments(round_, now=None):
    """One assignment for each active judge and each entry ready for judging, except the judge's
    own chapter's (Q17 A, S11). Safe to repeat; returns how many were added.
    """
    if round_.is_published:
        return 0
    entries = entries_for_judging(round_, now)
    judges = list(active_judges(round_))
    if not entries or not judges:
        return 0
    existing = set(Assignment.objects.filter(judge__round=round_).values_list("judge_id", "entry_id"))
    new = [
        Assignment(judge=judge, entry=entry)
        for judge in judges
        for entry in entries
        if judge.user.chapter_id != entry.chapter_id and (judge.pk, entry.pk) not in existing
    ]
    Assignment.objects.bulk_create(new, ignore_conflicts=True)
    return len(new)


def judge_rows(round_):
    """Every judge of the round with their progress: assigned, stepped aside, submitted, drafts."""
    counted = Q(assignments__stepped_aside_at__isnull=True)
    return (
        round_.judges.select_related("user", "user__chapter", "added_by")
        .annotate(
            assigned=Count("assignments", distinct=True),
            stepped_aside=Count("assignments", filter=Q(assignments__stepped_aside_at__isnull=False), distinct=True),
            submitted=Count(
                "assignments", filter=counted & Q(assignments__scorecard__submitted_at__isnull=False), distinct=True
            ),
            drafts=Count(
                "assignments",
                filter=counted
                & Q(assignments__scorecard__isnull=False, assignments__scorecard__submitted_at__isnull=True),
                distinct=True,
            ),
        )
        .order_by(F("removed_at").asc(nulls_first=True), "user__name")
    )


# --- Scorecards (NECCWI-10) ------------------------------------------------------------------


def scorecard_of(assignment):
    try:
        return assignment.scorecard
    except Scorecard.DoesNotExist:
        return None


def assignment_status(assignment):
    if assignment.stepped_aside_at is not None:
        return STEPPED_ASIDE
    card = scorecard_of(assignment)
    if card is None:
        return NOT_STARTED
    return SUBMITTED if card.submitted_at is not None else DRAFT


def assignment_of(user, entry):
    """``user``'s assignment to score ``entry`` while they are one of its round's judges, or None."""
    if not services.is_signed_in(user):
        return None
    return (
        Assignment.objects.filter(entry=entry, judge__user=user, judge__removed_at__isnull=True)
        .select_related("scorecard")
        .first()
    )


@dataclass
class RoundToDo:
    round: Round
    count: int
    deadline: str


@dataclass
class ScorecardsToDo:
    """The scorecards a judge still has to submit, drafts included, in rounds not yet published:
    the bubble at the top of every page and the nudge on the home page (S24).
    """

    rounds: list = field(default_factory=list)

    @property
    def count(self):
        return sum(row.count for row in self.rounds)

    def __bool__(self):
        return bool(self.rounds)


def scorecards_to_do(user):
    if not services.is_signed_in(user):
        return ScorecardsToDo()
    counts = dict(
        Assignment.objects.filter(
            judge__user=user,
            judge__removed_at__isnull=True,
            judge__round__results_published_at__isnull=True,
            judge__round__competition__is_published=True,
            stepped_aside_at__isnull=True,
            # Also true when there is no scorecard yet.
            scorecard__submitted_at__isnull=True,
        )
        .order_by()
        .values("judge__round")
        .annotate(count=Count("pk"))
        .values_list("judge__round", "count")
    )
    if not counts:
        return ScorecardsToDo()
    rounds = Round.objects.filter(pk__in=counts).select_related("competition").order_by("judging_closes_at", "pk")
    return ScorecardsToDo(
        [
            RoundToDo(
                round_,
                counts[round_.pk],
                round_.competition.format_time(round_.judging_closes_at) if round_.judging_closes_at else "",
            )
            for round_ in rounds
        ]
    )


@dataclass
class JudgingRound:
    judge: Judge
    rows: list
    to_do: int
    deadline: str


def judging_rounds(user):
    """My Judging: each round ``user`` judges, newest first, with its assignments and their status."""
    judges = (
        Judge.objects.active()
        .filter(user=user, round__competition__is_published=True)
        .select_related("round__competition")
        .order_by("-round__competition__year_label", "-round__number")
    )
    result = []
    for judge in judges:
        assignments = judge.assignments.select_related("entry__chapter__region", "scorecard").order_by(
            "entry__chapter__name"
        )
        rows = [(assignment, assignment_status(assignment)) for assignment in assignments]
        to_do = sum(1 for _, status in rows if status in (NOT_STARTED, DRAFT))
        competition = judge.round.competition
        result.append(JudgingRound(judge, rows, to_do, competition.format_time(judge.round.judging_closes_at)))
    return result


def can_open_scorecard(user, assignment):
    """The assigned judge, or a manager; judges never see each other's scorecards (S12)."""
    return services.is_signed_in(user) and (assignment.judge.user_id == user.pk or services.can_manage(user))


def can_score(user, assignment, now=None):
    """The assigned judge, still on the round, until the results are published (S13)."""
    judge = assignment.judge
    round_ = judge.round
    return (
        services.is_signed_in(user)
        and judge.user_id == user.pk
        and judge.removed_at is None
        and assignment.stepped_aside_at is None
        and not round_.is_published
        and services.judging_started(round_, assignment.entry, now)
    )


@transaction.atomic
def save_scorecard(assignment, scores, feedback, private_note="", submit=False, now=None):
    """Save a scorecard as a draft or submit it (S13). ``scores`` maps criterion ids to
    ``(points or None, comment)``.

    Submitting needs every criterion scored and the overall feedback (Q19); a submitted
    scorecard stays submitted when changed. The rubric locks on the first save (S15).
    """
    now = services._now(now)
    round_ = assignment.judge.round
    criteria = list(round_.criteria.all())
    card = Scorecard.objects.select_for_update().filter(assignment=assignment).first()
    submit = submit or (card is not None and card.submitted_at is not None)
    errors = []
    for criterion in criteria:
        points = scores.get(criterion.pk, (None, ""))[0]
        if points is not None and not round_.score_min <= points <= criterion.max_points:
            errors.append(f"{criterion.name}: give between {round_.score_min} and {criterion.max_points}.")
    if submit:
        missing = [criterion.name for criterion in criteria if scores.get(criterion.pk, (None, ""))[0] is None]
        if missing:
            errors.append(f"Score every criterion to submit. Still to score: {', '.join(missing)}.")
        if not (feedback or "").strip():
            errors.append("Write the overall feedback for the chapter to submit.")
    if errors:
        raise CompetitionError(" ".join(errors))
    if card is None:
        card = Scorecard.objects.create(assignment=assignment)
    for criterion in criteria:
        points, comment = scores.get(criterion.pk, (None, ""))
        CriterionScore.objects.update_or_create(
            scorecard=card, criterion=criterion, defaults={"points": points, "comment": (comment or "").strip()}
        )
    card.feedback = (feedback or "").strip()
    card.private_note = (private_note or "").strip()
    if submit:
        card.submitted_at = now
        card.total = sum(scores[criterion.pk][0] for criterion in criteria)
    card.save()
    Round.objects.filter(pk=round_.pk, rubric_locked_at__isnull=True).update(rubric_locked_at=now)
    return card


def step_aside(assignment, reason, now=None):
    """A judge steps aside from an entry, such as for a conflict of interest (S11)."""
    reason = (reason or "").strip()
    if not reason:
        raise CompetitionError("Give a reason, such as a conflict of interest. Only managers see it.")
    assignment.stepped_aside_at = services._now(now)
    assignment.step_aside_reason = reason
    assignment.save(update_fields=["stepped_aside_at", "step_aside_reason", "modified"])


def undo_step_aside(assignment):
    assignment.stepped_aside_at = None
    assignment.step_aside_reason = ""
    assignment.save(update_fields=["stepped_aside_at", "step_aside_reason", "modified"])


# --- Scores (NECCWI-11) ----------------------------------------------------------------------


def _average(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return (Decimal(sum(values)) / len(values)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def counted_scorecards(round_):
    """``{entry id: [scorecards]}``: submitted, from judges still on the round, not stepped aside."""
    cards = (
        Scorecard.objects.filter(
            assignment__entry__round=round_,
            submitted_at__isnull=False,
            assignment__judge__removed_at__isnull=True,
            assignment__stepped_aside_at__isnull=True,
        )
        .select_related("assignment__judge__user")
        .prefetch_related("scores__criterion")
        .order_by("assignment_id")
    )
    by_entry = defaultdict(list)
    for card in cards:
        by_entry[card.assignment.entry_id].append(card)
    return by_entry


@dataclass
class EntryScore:
    entry: Entry
    counted: list
    expected: int
    average: object
    # ``(criterion, its average)`` in rubric order.
    criterion_scores: list
    spread: object
    rank: object = None
    tied: bool = False

    @property
    def criterion_averages(self):
        return [average for _, average in self.criterion_scores]

    @property
    def missing(self):
        return max(self.expected - len(self.counted), 0)

    @property
    def region(self):
        return self.entry.chapter.region


def score_rows(round_):
    """``(criteria, rows)``: one row per submitted entry, by region, with averages and ranks."""
    criteria = list(round_.criteria.all())
    entries = services.entries_with_files(round_.entries.filter(submitted_at__isnull=False)).order_by(
        "chapter__region__name", "chapter__name"
    )
    cards = counted_scorecards(round_)
    expected = dict(
        Assignment.objects.filter(entry__round=round_, judge__removed_at__isnull=True, stepped_aside_at__isnull=True)
        .values("entry_id")
        .annotate(count=Count("pk"))
        .values_list("entry_id", "count")
    )
    rows = []
    for entry in entries:
        counted = cards.get(entry.pk, [])
        totals = [card.total for card in counted if card.total is not None]
        points = defaultdict(list)
        for card in counted:
            for score in card.scores.all():
                points[score.criterion_id].append(score.points)
        rows.append(
            EntryScore(
                entry=entry,
                counted=counted,
                expected=expected.get(entry.pk, 0),
                average=_average(totals),
                criterion_scores=[(criterion, _average(points[criterion.pk])) for criterion in criteria],
                spread=(max(totals) - min(totals)) if totals else None,
            )
        )
    _rank(rows)
    rows.sort(key=lambda row: (row.region.name, row.rank is None, row.rank or 0, row.entry.chapter.name))
    return criteria, rows


def _rank(rows):
    """Rank eligible, scored entries within each region ("1, 2, 2, 4"); equal averages are ties."""
    groups = defaultdict(list)
    for row in rows:
        if row.entry.eligible and row.average is not None:
            groups[row.entry.chapter.region_id].append(row)
    for group in groups.values():
        for row in group:
            row.rank = 1 + sum(1 for other in group if other.average > row.average)
            row.tied = sum(1 for other in group if other.average == row.average) > 1


def rows_by_region(rows):
    """``[(region, rows)]`` in region order, for the scores page."""
    groups = defaultdict(list)
    for row in rows:
        groups[row.region].append(row)
    return sorted(groups.items(), key=lambda pair: pair[0].name)


@dataclass
class Preselection:
    selected: set = field(default_factory=set)
    warnings: list = field(default_factory=list)


def preselect(round_, rows=None):
    """The top ``advance_per_region`` eligible entries in each region, at or above the minimum average
    (Q20 A). Nothing is dropped to meet the overall limit: the warnings say what to decide.
    """
    if rows is None:
        _, rows = score_rows(round_)
    limit, minimum = round_.advance_per_region, round_.min_average_to_advance
    result = Preselection()
    groups = defaultdict(list)
    for row in rows:
        if row.rank is not None:
            groups[row.region].append(row)
    for region, group in sorted(groups.items(), key=lambda pair: pair[0].name):
        if region.slug == NATIONAL_REGION_SLUG:
            result.warnings.append(
                f"{_plural(len(group), 'entry', 'entries')} from the {region} region, which has no regional limit: "
                "decide them by hand."
            )
            continue
        picks = [
            row for row in group if (limit is None or row.rank <= limit) and (minimum is None or row.average >= minimum)
        ]
        if limit is not None and len(picks) > limit:
            result.warnings.append(
                f"{region}: a tie at the limit puts {len(picks)} entries in {limit} places. Decide which advance."
            )
        result.selected |= {row.entry.pk for row in picks}
    if round_.advance_total is not None and len(result.selected) > round_.advance_total:
        result.warnings.append(
            f"The pre-selection has {len(result.selected)} entries; the most is {round_.advance_total}. "
            "Decide which advance."
        )
    return result


def selection_warnings(round_, rows):
    """What managers should check before publishing: limits, the minimum, ties and missing scorecards."""
    warnings = []
    eligible = [row for row in rows if row.entry.eligible]
    missing = [row for row in eligible if row.missing]
    if missing:
        warnings.append(f"{_plural(len(missing), 'entry is', 'entries are')} still missing scorecards.")
    if round_.selection == Round.Selection.ADVANCE:
        chosen = [row for row in eligible if row.entry.advanced]
        limit = round_.advance_per_region
        for region, count in sorted(Counter(row.region for row in chosen).items(), key=lambda pair: pair[0].name):
            if limit is not None and count > limit and region.slug != NATIONAL_REGION_SLUG:
                warnings.append(f"{region}: {count} qualifiers chosen; the most is {limit}.")
        if round_.advance_total is not None and len(chosen) > round_.advance_total:
            warnings.append(f"{len(chosen)} qualifiers chosen; the most is {round_.advance_total}.")
        minimum = round_.min_average_to_advance
        below = [row for row in chosen if minimum is not None and (row.average is None or row.average < minimum)]
        if below:
            warnings.append(f"{_plural(len(below), 'qualifier is', 'qualifiers are')} below the minimum average.")
        undecided = [row for row in eligible if row.entry.advanced is None]
        if undecided:
            warnings.append(
                f"{_plural(len(undecided), 'eligible entry has', 'eligible entries have')} no decision yet."
            )
    return warnings


def _decided(entry, by, now, fields):
    entry.decided_by = by
    entry.decided_at = services._now(now)
    entry.save(update_fields=[*fields, "decided_by", "decided_at", "modified"])


def _check_open_for_decisions(round_, selection):
    if round_.is_published:
        raise CompetitionError("The results are published, so the decisions are final.")
    if round_.selection != selection:
        raise CompetitionError("This round does not work that way.")


@transaction.atomic
def apply_preselection(round_, by, now=None):
    """Replace every eligible entry's decision with the pre-selection (Q20 A)."""
    _check_open_for_decisions(round_, Round.Selection.ADVANCE)
    _, rows = score_rows(round_)
    result = preselect(round_, rows)
    for row in rows:
        if row.entry.eligible:
            row.entry.advanced = row.entry.pk in result.selected
            _decided(row.entry, by, now, ["advanced"])
    return result


def set_decision(entry, advanced, by, now=None):
    """Qualified (True), not (False) or undecided (None)."""
    _check_open_for_decisions(entry.round, Round.Selection.ADVANCE)
    if advanced and not entry.eligible:
        raise CompetitionError("An ineligible entry cannot qualify.")
    entry.advanced = advanced
    _decided(entry, by, now, ["advanced"])


@transaction.atomic
def set_place(entry, place, by, now=None):
    """Record a place in a round that awards them; hidden from everyone else until announced (NECCWI-13)."""
    round_ = entry.round
    _check_open_for_decisions(round_, Round.Selection.PLACES)
    if place is not None:
        if not 1 <= place <= (round_.places or 0):
            raise CompetitionError(f"Choose a place from 1 to {round_.places}.")
        if not entry.eligible:
            raise CompetitionError("An ineligible entry cannot place.")
        Entry.objects.filter(round=round_, place=place).exclude(pk=entry.pk).update(place=None)
    entry.place = place
    _decided(entry, by, now, ["place"])


def set_eligibility(entry, eligible, reason, by, now=None):
    """Mark an entry ineligible, with a reason the chapter sees (S9), or eligible again."""
    if entry.round.is_published:
        raise CompetitionError("The results are published, so the decisions are final.")
    reason = (reason or "").strip()
    if not eligible and not reason:
        raise CompetitionError("Give the reason. The chapter sees it.")
    entry.eligible = eligible
    entry.ineligible_reason = "" if eligible else reason
    if not eligible:
        entry.advanced = None
        entry.place = None
    _decided(entry, by, now, ["eligible", "ineligible_reason", "advanced", "place"])


def set_hidden(obj, hidden):
    """Hide a judge's feedback (a ``Scorecard``) or one comment (a ``CriterionScore``) from the chapter (S18)."""
    name = "feedback_hidden" if isinstance(obj, Scorecard) else "comment_hidden"
    setattr(obj, name, hidden)
    obj.save(update_fields=[name, "modified"])


# --- Results (NECCWI-12, 13) -------------------------------------------------------------------


@dataclass
class JudgeFeedback:
    label: str
    feedback: str
    comments: list


def chapter_feedback(entry):
    """What the chapter reads once results are published (Q19, Q21): each counted judge's
    feedback and comments, unsigned ("Judge 1"), with hidden ones left out.
    """
    round_ = entry.round
    if not round_.is_published or not round_.share_feedback:
        return []
    rows = []
    for number, card in enumerate(counted_scorecards(round_).get(entry.pk, []), start=1):
        comments = [
            (score.criterion.name, score.comment)
            for score in sorted(card.scores.all(), key=lambda score: (score.criterion.order, score.criterion_id))
            if score.comment and not score.comment_hidden
        ]
        feedback = "" if card.feedback_hidden else card.feedback
        if feedback or comments:
            rows.append(JudgeFeedback(f"Judge {number}", feedback, comments))
    return rows


def chapter_scores(entry):
    """The scores a chapter sees after results, as the round allows (Q21): its average, each
    criterion's average and its rank in its region. ``None`` when the round shares none.
    """
    round_ = entry.round
    if not round_.is_published or not (round_.share_scores or round_.share_rank):
        return None
    _, rows = score_rows(round_)
    row = next((row for row in rows if row.entry.pk == entry.pk), None)
    if row is None:
        return None
    return {
        "average": row.average if round_.share_scores else None,
        "criteria": row.criterion_scores if round_.share_scores else [],
        "rank": row.rank if round_.share_rank else None,
        "tied": row.tied,
        "region_count": sum(1 for other in rows if other.region == row.region and other.rank is not None),
    }


def result_label(entry):
    """The chapter's result once published, in a few words; None before."""
    round_ = entry.round
    if not round_.is_published or entry.submitted_at is None:
        return None
    if not entry.eligible:
        return "Not eligible"
    if round_.selection == Round.Selection.ADVANCE:
        return "Regional Qualifier" if entry.advanced else "Not selected"
    return f"{ordinal(entry.place)} place" if entry.place else "Finalist"


def showcase(round_):
    """The entries everyone signed in sees once results are published (Q22 A), best first."""
    if not round_.is_published:
        return []
    entries = round_.entries.filter(eligible=True).select_related("chapter__region")
    if round_.selection == Round.Selection.ADVANCE:
        return list(entries.filter(advanced=True).order_by("chapter__region__name", "chapter__name"))
    return list(entries.filter(submitted_at__isnull=False).order_by(F("place").asc(nulls_last=True), "chapter__name"))


def publish_blockers(round_, rows=None):
    """What must be done before publishing: a decision on every eligible entry, or every place filled."""
    if rows is None:
        _, rows = score_rows(round_)
    eligible = [row for row in rows if row.entry.eligible]
    if round_.selection == Round.Selection.ADVANCE:
        undecided = [row for row in eligible if row.entry.advanced is None]
        if undecided:
            return [
                f"Decide every eligible entry first: {_plural(len(undecided), 'entry has', 'entries have')} "
                "no decision."
            ]
        return []
    taken = {row.entry.place for row in rows if row.entry.place}
    open_places = [ordinal(place) for place in range(1, (round_.places or 0) + 1) if place not in taken]
    if open_places:
        return [f"Choose the entry for each place first: {', '.join(open_places)} place still open."]
    return []


@transaction.atomic
def publish_results(round_, by, now=None):
    """Publish a round's results, or announce the winners of a round awarding places.

    Locks the scorecards, shows each chapter its result, showcases the selected entries
    (Q22 A), emails each chapter (E9, or E10 for the winners) once the request commits and
    records the awards (Q24 A). Publishing twice does nothing more.
    """
    round_ = Round.objects.select_for_update().select_related("competition").get(pk=round_.pk)
    if round_.is_published:
        return False
    blockers = publish_blockers(round_)
    if blockers:
        raise CompetitionError(" ".join(blockers))
    now = services._now(now)
    round_.results_published_at = now
    round_.results_published_by = by
    round_.save(update_fields=["results_published_at", "results_published_by", "modified"])
    grant_awards(round_, by, now)
    transaction.on_commit(lambda: send_results(round_.pk))
    return True


def send_results(round_id):
    """E9 (or E10 for a round awarding places) to each chapter with an entry, once per chapter."""
    from .notifications import ChapterResult, WinnersAnnounced, send_once

    round_ = Round.objects.select_related("competition").filter(pk=round_id).first()
    if round_ is None or not round_.is_published:
        return 0
    competition = round_.competition
    entries = round_.entries.filter(Q(submitted_at__isnull=False) | Q(eligible=False)).select_related("chapter")
    sent = 0
    if round_.selection == Round.Selection.ADVANCE:
        for entry in entries:
            key = f"{Kind.RESULTS}:{round_.pk}:{entry.chapter_id}"
            sent += send_once(ChapterResult(entry), key, Kind.RESULTS, competition, round_, entry.chapter)
        return sent
    winners = list(round_.entries.filter(place__isnull=False).select_related("chapter").order_by("place"))
    for entry in entries:
        key = f"{Kind.WINNERS}:{round_.pk}:{entry.chapter_id}"
        sent += send_once(WinnersAnnounced(entry, winners), key, Kind.WINNERS, competition, round_, entry.chapter)
    return sent


def award_type_for(name):
    """The award type named ``name``, made from ``AWARD_TYPE_DEFAULTS`` when it is missing."""
    from thetatauCMT.awards.models import AwardType

    award_type = AwardType.objects.filter(name__iexact=name).first()
    if award_type is not None:
        return award_type
    return AwardType.objects.create(
        name=name,
        category="Case Competition",
        level=AwardType.Level.CHAPTER,
        grant_method=AwardType.GrantMethod.DIRECT,
        recurrence=AwardType.Recurrence.RECURRING,
        **AWARD_TYPE_DEFAULTS[name],
    )


def grant_awards(round_, by, now=None):
    """Record the results as chapter awards (Q24 A), once each, when awards are switched on.

    Regional Qualifiers get the award quietly: the results email (E9) already tells them, and
    up to 20 home-page announcements at once would crowd the home page. The winners' awards
    fire ``award_granted``, so they are announced like every other award (S33).
    """
    from thetatauCMT.awards.models import AwardGrant
    from thetatauCMT.awards.services import grant_award, resolve_or_create_year_cycle
    from thetatauCMT.awards.signals import award_granted
    from thetatauCMT.configs.models import Config

    if not Config.feature_enabled("FEATURE_AWARDS"):
        return []
    competition = round_.competition
    granted_by = by or services.competition_contact(competition).user
    if granted_by is None:
        logger.warning("Nobody to record as granting the Case Competition awards for %s; none recorded", round_)
        return []
    if round_.selection == Round.Selection.ADVANCE:
        winners = [(QUALIFIER_AWARD, entry) for entry in round_.entries.filter(advanced=True, eligible=True)]
        announce = False
    else:
        places = round_.entries.filter(place__in=PLACE_AWARDS, eligible=True)
        winners = [(PLACE_AWARDS[entry.place], entry) for entry in places]
        announce = True
    cycle = resolve_or_create_year_cycle(competition.local(services._now(now)).year)
    grants = []
    for name, entry in winners:
        award_type = award_type_for(name)
        if AwardGrant.objects.filter(award_type=award_type, cycle=cycle, recipient_chapter=entry.chapter).exists():
            continue
        reason = f"{competition.name} {competition.year_label}: {entry.title}"
        grant = grant_award(
            award_type, cycle, entry.chapter, granted_by, reason=reason, source=AwardGrant.Source.DIRECT
        )
        if announce:
            transaction.on_commit(
                lambda grant=grant: award_granted.send(sender=AwardGrant, grant=grant, actor=granted_by)
            )
        grants.append(grant)
    return grants


# --- The daily run: judges' emails (E7, E8) and late assignments -----------------------------


def daily(round_, run):
    """Once judging has started: add late assignments, then E7 once per judge and the E8 ladder."""
    from .notifications import JudgeNotice
    from .reminders import current_step, judge_steps

    if not services.judging_started(round_, now=run.now):
        return
    competition = round_.competition
    if not run.dry_run:
        added = sync_assignments(round_, run.now)
        if added:
            run.lines.append(f"Added {added} judging assignment(s) for {round_}")
    step = current_step(judge_steps(round_), run.now)
    for judge in judge_rows(round_).filter(removed_at__isnull=True):
        assigned = judge.assigned - judge.stepped_aside
        to_do = assigned - judge.submitted
        if assigned <= 0:
            continue
        opened = run.send(
            lambda: JudgeNotice(judge, Kind.JUDGING_OPEN, to_do, assigned, run.now),
            f"{Kind.JUDGING_OPEN}:{round_.pk}:{judge.user_id}",
            Kind.JUDGING_OPEN,
            competition,
            round_,
            user=judge.user,
            to_label=f"{round_} to {judge.user}",
        )
        if opened or to_do <= 0 or step is None:
            continue
        run.send(
            lambda: JudgeNotice(judge, Kind.JUDGING_DUE, to_do, assigned, run.now),
            step.key(round_, judge.user_id),
            Kind.JUDGING_DUE,
            competition,
            round_,
            user=judge.user,
            to_label=f"{round_} to {judge.user}",
        )
