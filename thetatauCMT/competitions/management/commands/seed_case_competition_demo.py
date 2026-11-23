"""A demo Case Competition for local QA (NECCWI-8, 14). Never run it in production.

    docker exec thetataucmt_local_django python manage.py seed_case_competition_demo
    docker exec thetataucmt_local_django python manage.py seed_case_competition_demo --stage judging --judge you@example.com

Builds (or rebuilds) the published competition ``necc-demo`` with this year's rounds, rubric
and files to collect, read from the ``necc_2026_2027`` fixture, and eight chapters from three
regions. Every date is relative to today, so the chosen stage is current:

``open``
    The proposal window is open: three entries are complete and two are in progress.
``judging``
    The proposal window closed three days ago. Six entries are complete, one is incomplete
    and one chapter submitted nothing. Three demo judges are part way through: Avery has a
    draft left; Blake stepped aside from an entry and has a draft and one to start; Casey has
    not started. Two entries in the first region tie for second place.
``results``
    Every scorecard is in, the Regional Qualifiers are published (the manager overrode the
    pre-selection for one entry) and the final window is open.
``final``
    The final round is closed and judged, with places chosen but not announced.

The demo judges sign in as ``necc-judge-avery@demo.thetatau.local`` (also ``-blake`` and
``-casey``) with the password ``necc-demo-judge``. Casey is an alumna of a chapter taking part,
so is never given its entry. ``--judge`` makes existing accounts judges too, with nothing
scored, so you can score with your own sign-in.
"""

import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from allauth.account.models import EmailAddress
from django.core import serializers
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from core.models import ALUMNI_STATUSES
from core.seed_guard import ensure_seeding_allowed
from thetatauCMT.awards.models import AwardGrant
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.competitions import judging, services
from thetatauCMT.competitions.forms import chapter_members
from thetatauCMT.competitions.models import (
    DEFAULT_TIME_ZONE,
    Assignment,
    Competition,
    EntryMember,
    KeyDate,
    Participant,
    Round,
    RubricCriterion,
    SubmissionItem,
)
from thetatauCMT.users.models import User

SLUG = "necc-demo"
YEAR_LABEL = "Demo"
STAGES = ("open", "judging", "results", "final")
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "necc_2026_2027.json"
DEMO_EMAIL_DOMAIN = "demo.thetatau.local"
DEMO_PASSWORD = "necc-demo-judge"
DEMO_JUDGES = (("Avery", "Lin"), ("Blake", "Okafor"), ("Casey", "Morgan"))
AVERY, BLAKE, CASEY = range(len(DEMO_JUDGES))

# Days from today: the proposal window (opens, closes, judging deadline), then the final's.
SCHEDULE = {
    "open": ((-3, 6, 30), (60, 67, 95)),
    "judging": ((-12, -3, 21), (51, 58, 86)),
    "results": ((-43, -34, -10), (-2, 5, 33)),
    "final": ((-103, -94, -70), (-10, -3, 20)),
}

COMPLETE, PARTIAL, NOTHING = "complete", "partial", ""
INTENT, NATIONAL, FIRST_ENTRY = Participant.Source.INTENT, Participant.Source.ADMIN, Participant.Source.SUBMISSION
# One row per chapter: its region (0 is the region with the most chapters), how it registered,
# and its proposal while the window is open and once it has closed.
LAYOUT = (
    (0, INTENT, COMPLETE, COMPLETE),
    (0, INTENT, PARTIAL, COMPLETE),
    (0, NATIONAL, NOTHING, COMPLETE),
    (0, INTENT, PARTIAL, PARTIAL),
    (1, INTENT, COMPLETE, COMPLETE),
    (1, NATIONAL, NOTHING, NOTHING),
    (2, FIRST_ENTRY, COMPLETE, COMPLETE),
    (2, INTENT, NOTHING, COMPLETE),
)
CASEY_HOME_ROW = 2
TITLES = (
    "Smart lighting retrofit for the engineering library",
    "Solar-assisted water heating for campus housing",
    "Energy dashboards for the residence halls",
    "Free energy audits for local small businesses",
    "Heat-pump conversion study for the chapter house",
    "Cutting plug loads in campus labs",
    "Weatherizing homes with a local nonprofit",
    "Demand-controlled ventilation for lecture halls",
)

SUBMITTED, DRAFT = "submitted", "draft"
# Proposal totals out of 35 (seven criteria scored 1 to 5) from Avery, Blake and Casey, by row.
# Blake steps aside from row 1, and Casey is never given row 2, her own chapter's entry.
PROPOSAL_TOTALS = {
    0: (31, 29, 32),
    1: (27, None, 29),
    2: (26, 28, None),
    4: (24, 25, 26),
    6: (22, 23, 21),
    7: (29, 30, 31),
}
STEP_ASIDE = {(BLAKE, 1): "Conflict of interest: I mentored this team over the summer."}
# At the judging stage, what each judge has done so far; every other assignment is not started.
# Rows 1 and 2 then tie for second place in their region, which has two places.
JUDGING_PROGRESS = {
    AVERY: {0: SUBMITTED, 1: SUBMITTED, 2: SUBMITTED, 4: SUBMITTED, 6: SUBMITTED, 7: DRAFT},
    BLAKE: {0: SUBMITTED, 2: SUBMITTED, 4: DRAFT, 7: SUBMITTED},
    CASEY: {},
}
# The pre-selection qualifies this row, but the manager decides it does not.
OVERRIDDEN_ROW = 6
# The final round, for the qualifiers: each one's entry while the window is open and once it
# has closed, then the totals out of 25 (five criteria) and the places chosen.
FINAL_ENTRIES = {0: (COMPLETE, COMPLETE), 1: (NOTHING, COMPLETE), 4: (PARTIAL, PARTIAL), 7: (NOTHING, COMPLETE)}
FINAL_TOTALS = {0: (21, 22, 20), 1: (18, 19, 17), 7: (23, 24, 22)}
FINAL_PLACES = {7: 1, 0: 2}

FEEDBACK = (
    "A clear, well-scoped problem with a credible baseline. Tighten the cost estimate before you build.",
    "Strong technical analysis. Set specific targets for the measurements and a date for each.",
    "A creative approach with wide chapter involvement. Cite the sources behind the savings estimate.",
    "Practical and well organized. Explain how the project carries on after the competition.",
)
COMMENTS = (
    "Add the sources behind these numbers.",
    "Clear and well supported.",
    "Needs more detail on cost and schedule.",
    "Say how you will measure this.",
)
DRAFT_FEEDBACK = "A strong start. Still writing my notes on the budget."
PRIVATE_NOTE = "A good candidate to present at Convention."
DEMO_NOTE = "<p><em>A demo for local testing. Its dates move with the stage it was built at.</em></p>"

COMPETITION_FIELDS = (
    "name",
    "short_name",
    "case_title",
    "case_description",
    "about",
    "resources",
    "contact_role",
    "time_zone",
)
ROUND_FIELDS = (
    "number",
    "name",
    "selection",
    "eligibility",
    "instructions",
    "grace_minutes",
    "score_min",
    "advance_per_region",
    "advance_total",
    "min_average_to_advance",
    "places",
    "share_feedback",
    "share_scores",
    "share_rank",
    "reminder_days_before_open",
    "reminder_days_before_close",
    "judge_reminder_days",
)
CRITERION_FIELDS = ("name", "description", "max_points", "order")
ITEM_FIELDS = ("label", "description", "kind", "file_types", "max_size_mb", "required", "order")


def at_eastern(days, hour=0, minute=0):
    zone = ZoneInfo(DEFAULT_TIME_ZONE)
    day = timezone.localtime(timezone.now() + datetime.timedelta(days=days), zone).date()
    return datetime.datetime.combine(day, datetime.time(hour, minute), tzinfo=zone)


def read_fixture():
    """This year's competition, and each round with its rubric and files to collect, unsaved."""
    objects = [item.object for item in serializers.deserialize("json", FIXTURE.read_text(encoding="utf-8"))]
    competition = next(obj for obj in objects if isinstance(obj, Competition))
    rounds = sorted((obj for obj in objects if isinstance(obj, Round)), key=lambda round_: round_.number)
    return competition, [
        (
            round_,
            [obj for obj in objects if isinstance(obj, RubricCriterion) and obj.round_id == round_.pk],
            [obj for obj in objects if isinstance(obj, SubmissionItem) and obj.round_id == round_.pk],
        )
        for round_ in rounds
    ]


def copy_fields(source, names):
    return {name: getattr(source, name) for name in names}


def split_total(total, count, shift):
    """``count`` scores adding up to ``total``, as even as can be; ``shift`` moves the higher ones."""
    base, extra = divmod(total, count)
    return [base + (1 if (position + shift) % count < extra else 0) for position in range(count)]


def demo_pdf(*lines):
    """A one-page PDF showing ``lines``, so a demo file opens like a real one."""

    def text(line):
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    commands = ["BT", "/F1 18 Tf", "72 720 Td", f"({text(lines[0])}) Tj", "/F1 12 Tf"]
    for line in lines[1:]:
        commands += ["0 -24 Td", f"({text(line)}) Tj"]
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", "replace")
    bodies = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(bodies, start=1):
        offsets.append(len(pdf))
        pdf += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    start = len(pdf)
    pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(bodies) + 1)
    pdf += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    pdf += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(bodies) + 1, start)
    return bytes(pdf)


class Command(BaseCommand):
    help = "Build the demo Case Competition 'necc-demo' for local QA, at a chosen stage. Never in production."

    def add_arguments(self, parser):
        parser.add_argument("--stage", choices=STAGES, default="open", help="Which moment to build (default open).")
        parser.add_argument(
            "--judge",
            action="append",
            default=[],
            metavar="EMAIL",
            help="Make this existing account a judge too, with nothing scored. Repeat it for more.",
        )
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG is off.")

    def handle(self, *args, **options):
        ensure_seeding_allowed(force=options["force"])
        stage = options["stage"]
        extra = [self.find_user(identifier) for identifier in options["judge"]]
        rows, spare = self.pick_rows()
        with transaction.atomic():
            competition = self.build(stage, rows, spare, extra)
        self.report(competition, stage, rows)

    def find_user(self, identifier):
        user = (
            User.objects.filter(Q(username__iexact=identifier) | Q(email__iexact=identifier), is_active=True)
            .order_by("pk")
            .first()
        )
        if user is None:
            raise CommandError(f"No active account has the email or username {identifier!r}.")
        return user

    def pick_rows(self):
        """A chapter for each ``LAYOUT`` row, and the chapters left over.

        Only active chapters with three current members count. The regions with the most of
        them come first, so the first region has four entries to rank.
        """
        regions = {}
        chapters = Chapter.objects.filter(active=True, region__isnull=False).select_related("region")
        for chapter in chapters.order_by("name"):
            if chapter_members(chapter).count() >= 3:
                regions.setdefault(chapter.region, []).append(chapter)
        ordered = sorted(regions.values(), key=lambda group: (-len(group), group[0].region.name))
        everyone = [chapter for group in ordered for chapter in group]
        rows, used = [], set()
        for layout in LAYOUT:
            preferred = ordered[layout[0]] if layout[0] < len(ordered) else []
            chapter = next((chapter for chapter in preferred + everyone if chapter.pk not in used), None)
            if chapter is None:
                raise CommandError(
                    f"Needs {len(LAYOUT)} active chapters with at least three current members each, "
                    "ideally from three regions."
                )
            used.add(chapter.pk)
            rows.append((chapter, layout))
        return rows, [chapter for chapter in everyone if chapter.pk not in used]

    def build(self, stage, rows, spare, extra):
        details, rounds = read_fixture()
        # The last demo, with the awards its published results recorded.
        AwardGrant.objects.filter(reason__startswith=f"{details.name} {YEAR_LABEL}: ").delete()
        Competition.objects.filter(slug=SLUG).delete()
        proposal_days, final_days = SCHEDULE[stage]
        fields = copy_fields(details, COMPETITION_FIELDS)
        fields["about"] = DEMO_NOTE + fields["about"]
        competition = Competition.objects.create(
            slug=SLUG,
            year_label=YEAR_LABEL,
            intent_opens_at=at_eastern(proposal_days[0] - 57),
            intent_closes_at=at_eastern(proposal_days[0] - 27, 23, 59),
            is_published=True,
            **fields,
        )
        KeyDate.objects.create(competition=competition, date=at_eastern(proposal_days[0] - 40).date(), label="Live Q&A")
        proposal = self.add_round(competition, rounds[0], proposal_days)
        final = self.add_round(competition, rounds[1], final_days)
        manager = User.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
        for index, (chapter, (_, source, while_open, after_close)) in enumerate(rows):
            if source != FIRST_ENTRY:
                self.register(competition, chapter, source, manager, index)
            plan = while_open if stage == "open" else after_close
            if plan:
                self.add_entry(proposal, chapter, plan == COMPLETE, index)
        home = spare[0] if spare else rows[-1][0]
        judges = [
            self.demo_judge(first, last, rows[CASEY_HOME_ROW][0] if number == CASEY else home)
            for number, (first, last) in enumerate(DEMO_JUDGES)
        ]
        # Extra judges join the round being judged, so their list never has a published round to do.
        proposal_judges = judges + extra if stage in ("open", "judging") else judges
        for user in proposal_judges:
            judging.add_judge(proposal, user, by=manager)
        if stage == "open":
            return competition
        progress = JUDGING_PROGRESS if stage == "judging" else None
        self.judge(proposal, rows, judges, PROPOSAL_TOTALS, progress, STEP_ASIDE)
        if stage == "judging":
            return competition
        judging.apply_preselection(proposal, manager)
        judging.set_decision(proposal.entries.get(chapter=rows[OVERRIDDEN_ROW][0]), False, manager)
        judging.publish_results(proposal, manager)
        for user in judges + extra:
            judging.add_judge(final, user, by=manager)
        qualifiers = services.qualifier_chapter_ids(final)
        for index, (while_open, after_close) in FINAL_ENTRIES.items():
            chapter = rows[index][0]
            plan = while_open if stage == "results" else after_close
            if plan and chapter.pk in qualifiers:
                self.add_entry(final, chapter, plan == COMPLETE, index)
        if stage == "results":
            return competition
        self.judge(final, rows, judges, FINAL_TOTALS)
        for index, place in FINAL_PLACES.items():
            entry = final.entries.filter(chapter=rows[index][0], submitted_at__isnull=False).first()
            if entry is not None:
                judging.set_place(entry, place, manager)
        return competition

    def add_round(self, competition, spec, days):
        template, criteria, items = spec
        opens, closes, judged = days
        round_ = Round.objects.create(
            competition=competition,
            opens_at=at_eastern(opens),
            closes_at=at_eastern(closes, 23, 59),
            judging_closes_at=at_eastern(judged, 23, 59),
            **copy_fields(template, ROUND_FIELDS),
        )
        RubricCriterion.objects.bulk_create(
            RubricCriterion(round=round_, **copy_fields(criterion, CRITERION_FIELDS)) for criterion in criteria
        )
        SubmissionItem.objects.bulk_create(
            SubmissionItem(round=round_, **copy_fields(item, ITEM_FIELDS)) for item in items
        )
        return round_

    def register(self, competition, chapter, source, manager, index):
        contact = chapter_members(chapter).first()
        by_chapter = source == INTENT
        services.register(
            competition,
            chapter,
            by=contact if by_chapter else manager,
            source=source,
            contacts=[contact],
            team_size_estimate=3 + index % 4 if by_chapter else None,
            note="We hope to bring first-year members onto the team." if index == 0 else None,
            welcome=False,
        )

    def add_entry(self, round_, chapter, complete, index):
        """Save the chapter's entry: complete, or with its last required file missing."""
        members = list(chapter_members(chapter)[:3])
        required = list(round_.items.filter(kind=SubmissionItem.Kind.FILE, required=True))
        title = TITLES[index % len(TITLES)]
        uploads = {
            item: ContentFile(
                demo_pdf(title, chapter.full_name, f"{round_.name}: {item.label}", "A demo file for local testing."),
                name=f"{chapter.slug}-{slugify(item.label)}.pdf",
            )
            for item in (required if complete else required[:-1])
        }
        video = round_.items.filter(kind=SubmissionItem.Kind.LINK).first()
        links = (
            {video: f"https://example.com/necc-demo/{chapter.slug}"} if complete and video and index % 2 == 0 else {}
        )
        when = min(
            timezone.now() - datetime.timedelta(hours=1 + 6 * index),
            round_.closes_at - datetime.timedelta(hours=2 + 9 * index),
        )
        result = services.save_entry(
            round_,
            chapter,
            members[0],
            title=title,
            summary="What we will build, the baseline we will measure it against, the budget, and who does what.",
            uploads=uploads,
            links=links,
            now=when,
        )
        for order, person in enumerate(members):
            EntryMember.objects.get_or_create(
                entry=result.entry,
                user=person,
                defaults={"team_role": "Team lead" if order == 0 else "Team member", "order": order},
            )
        return result.entry

    def demo_judge(self, first, last, chapter):
        """A demo alumnus who can sign in; alumni without a role need not sign the policies."""
        email = f"necc-judge-{first.lower()}@{DEMO_EMAIL_DOMAIN}"
        user = User.objects.filter(username=email).first() or User(username=email, email=email)
        user.first_name, user.last_name, user.name = first, last, f"[DEMO] {first} {last}"
        user.chapter = chapter
        user.is_active = True
        user.set_password(DEMO_PASSWORD)
        user.save()
        if user.current_status not in ALUMNI_STATUSES:
            user.set_current_status("alumni", start=timezone.localdate() - datetime.timedelta(days=3 * 365))
        EmailAddress.objects.get_or_create(user=user, email=email, defaults={"verified": True, "primary": True})
        return user

    def judge(self, round_, rows, judges, totals, progress=None, step_asides=None):
        """Score ``round_`` from ``totals``: all of it, or with ``progress`` what each judge has done so far."""
        judging.sync_assignments(round_)
        row_of = {chapter.pk: index for index, (chapter, _) in enumerate(rows)}
        number_of = {user.pk: number for number, user in enumerate(judges)}
        assignments = (
            Assignment.objects.filter(judge__round=round_, judge__user__in=judges)
            .select_related("judge__round", "entry")
            .order_by("judge__user__name", "entry__chapter__name")
        )
        when = round_.closes_at
        for assignment in assignments:
            number, index = number_of[assignment.judge.user_id], row_of[assignment.entry.chapter_id]
            when = min(when + datetime.timedelta(hours=2), timezone.now())
            reason = (step_asides or {}).get((number, index))
            if reason:
                judging.step_aside(assignment, reason, now=when)
                continue
            state = SUBMITTED if progress is None else progress[number].get(index)
            total = totals.get(index, (None,) * len(judges))[number]
            if state is not None and total is not None:
                self.score(assignment, total, state == SUBMITTED, number + index, when)

    def score(self, assignment, total, submit, variant, when):
        criteria = list(assignment.judge.round.criteria.all())
        points = split_total(total, len(criteria), variant)
        if not submit:
            half = (len(criteria) + 1) // 2
            points = points[:half] + [None] * (len(criteria) - half)
        scores = {criterion.pk: (value, "") for criterion, value in zip(criteria, points)}
        scores[criteria[0].pk] = (points[0], COMMENTS[variant % len(COMMENTS)])
        feedback = FEEDBACK[variant % len(FEEDBACK)] if submit else DRAFT_FEEDBACK
        note = PRIVATE_NOTE if submit and variant % 5 == 0 else ""
        judging.save_scorecard(assignment, scores, feedback, note, submit=submit, now=when)

    def report(self, competition, stage, rows):
        number = 1 if stage in ("open", "judging") else 2
        round_ = competition.rounds.get(number=number)
        self.stdout.write(f"Built {competition} at the '{stage}' stage: /competitions/{SLUG}/")
        self.stdout.write("Chapters: " + ", ".join(chapter.name for chapter, _ in rows))
        self.stdout.write(f"Judges of the {round_.name} (the demo judges' password is {DEMO_PASSWORD!r}):")
        for judge in judging.judge_rows(round_):
            to_start = judge.assigned - judge.stepped_aside - judge.submitted - judge.drafts
            self.stdout.write(
                f"  {judge.user.email} ({judge.user.chapter}): {judge.assigned} assigned, "
                f"{judge.submitted} submitted, {judge.drafts} drafts, {judge.stepped_aside} stepped aside, "
                f"{to_start} to start"
            )
        self.stdout.write(
            f"Judges start at /competitions/judging/; managers at /competitions/{SLUG}/round/{number}/judges/ "
            f"and /competitions/{SLUG}/round/{number}/scores/"
        )
