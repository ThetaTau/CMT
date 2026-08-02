"""Management command that seeds the local DB with rich, realistic dashboard data.

Idempotent guardrails:
- Every seed user gets email `<slug>-<n>@seed.thetatau.local`
- Every seed chapter's `school` starts with `"[SEED] "`
- Every seed region's `name` starts with `"[SEED] "`
- `--reset` deletes ONLY objects matching these markers so real production
  data stays intact.

Usage examples:
    podman exec thetataucmt_local_django python manage.py seed_dashboard_data
    podman exec thetataucmt_local_django python manage.py seed_dashboard_data --reset
    podman exec thetataucmt_local_django python manage.py seed_dashboard_data \\
        --regions 6 --chapters-per-region 5 --users-per-chapter 50
"""

import datetime
import random
import uuid

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from core.models import academic_encompass_start_end_date
from core.seed_guard import ensure_seeding_allowed
from thetatauCMT.chapters.models import Chapter, ChapterCurricula
from thetatauCMT.events.models import Event
from thetatauCMT.forms.models import Badge, Depledge, Guard, Initiation, PrematureAlumnus, ResignationProcess
from thetatauCMT.regions.models import Region
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.submissions.models import Submission
from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate
from thetatauCMT.trainings.models import Training
from thetatauCMT.users.models import User, UserSemesterGPA, UserStatusChange

SEED_REGION_PREFIX = "[SEED] "
SEED_SCHOOL_PREFIX = "[SEED] "
SEED_EMAIL_DOMAIN = "seed.thetatau.local"
SEED_TASK_PREFIX = "[SEED] "

REGION_NAMES = ["Northeast", "Southeast", "Midwest", "South Central", "West", "Northwest"]
CHAPTER_ROOTS = [
    "Alpha",
    "Beta",
    "Gamma",
    "Delta",
    "Epsilon",
    "Zeta",
    "Eta",
    "Theta",
    "Iota",
    "Kappa",
    "Lambda",
    "Mu",
    "Nu",
    "Xi",
    "Omicron",
    "Pi",
    "Rho",
    "Sigma",
    "Tau",
    "Upsilon",
    "Phi",
    "Chi",
    "Psi",
    "Omega",
]
MAJORS = [
    "Mechanical Engineering",
    "Electrical Engineering",
    "Computer Science",
    "Civil Engineering",
    "Chemical Engineering",
    "Aerospace Engineering",
    "Biomedical Engineering",
    "Industrial Engineering",
    "Environmental Engineering",
    "Materials Science",
]

# Faker gives us broad name variety without a hand-maintained wordlist.
_faker = Faker()


def _dt(d):
    """Make a date/datetime timezone-aware if settings.USE_TZ is on."""
    if isinstance(d, datetime.date) and not isinstance(d, datetime.datetime):
        d = datetime.datetime.combine(d, datetime.time())
    if timezone.is_naive(d) and getattr(settings, "USE_TZ", False):
        return timezone.make_aware(d)
    return d


def _random_date_in_range(start, end):
    """Return a `datetime.date` uniformly between the two datetimes."""
    delta = (end - start).days
    return (start + datetime.timedelta(days=random.randint(0, max(0, delta - 1)))).date()


def _jitter(base, spread=0.25, floor=0):
    """Return `base` +/- a random Gaussian jitter.

    `spread` is the standard deviation as a fraction of the base value, so
    ~68% of results land within +/- (spread * base). Clamped to `floor` so
    negative counts never leak into the seed.
    """
    if base <= 0:
        return floor
    value = int(round(random.gauss(base, base * spread)))
    return max(floor, value)


class Command(BaseCommand):
    help = "Seed the local DB with fake regions, chapters, members, and activity for dashboard QA."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing seed data before creating.")
        parser.add_argument("--regions", type=int, default=5, help="Number of seed regions (default 5).")
        parser.add_argument("--chapters-per-region", type=int, default=4, help="Chapters per region (default 4).")
        parser.add_argument("--users-per-chapter", type=int, default=40, help="Users per chapter (default 40).")
        parser.add_argument("--events-per-chapter", type=int, default=8, help="Events per chapter this AY (default 8).")
        parser.add_argument(
            "--submissions-per-chapter",
            type=int,
            default=4,
            help="Submissions per chapter this AY (default 4).",
        )
        parser.add_argument(
            "--tasks-per-chapter",
            type=int,
            default=6,
            help="Task completions per chapter this AY (default 6).",
        )
        parser.add_argument(
            "--trainings-per-user",
            type=int,
            default=1,
            help="Completed trainings per active user this AY (default 1).",
        )
        parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Required to run when settings.DEBUG is off (production-like).",
        )

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def handle(self, *args, **opts):
        ensure_seeding_allowed(opts["force"])
        if opts["seed"] is not None:
            random.seed(opts["seed"])

        ay_start, ay_end = academic_encompass_start_end_date()
        now = timezone.now()
        # academic_encompass_start_end_date returns naive datetimes; make them
        # aware so they can be compared to `timezone.now()` without TypeError.
        ay_start = _dt(ay_start)
        ay_end = _dt(ay_end)
        # Activity (events / submissions / tasks / trainings) spans a WIDE
        # window from ~4 years ago through the END of the current AY so:
        #   - Multiple past AYs on the region dashboard's AY selector have
        #     real activity data instead of empty bars.
        #   - The Chapter Activity page (`/chapters/<slug>/activity/`) has
        #     recent past events for its default 6-month lookback AND
        #     events dated inside the CURRENT AY / CURRENT TERM windows
        #     (which include future dates on the calendar). Without the
        #     future half, filtering to `current academic year` on a fresh
        #     seed near July would show only the couple of days that had
        #     already passed.
        activity_start = _dt(now - datetime.timedelta(days=365 * 4))
        activity_end = ay_end
        # `today` is used to decide which UserStatusChange rows should mark a
        # user's `current_status`.
        today = now.date()

        self.stdout.write(self.style.MIGRATE_HEADING(f"Academic year window: {ay_start.date()} → {ay_end.date()}"))

        if opts["reset"]:
            self._reset_seed_data()

        with transaction.atomic():
            regions = self._create_regions(opts["regions"])
            chapters = self._create_chapters(regions, opts["chapters_per_region"])
            self.stdout.write(self.style.SUCCESS(f"  Regions: {len(regions)}   Chapters: {len(chapters)}"))

            users_created = 0
            initiations = 0
            depledges = 0
            prealums = 0
            resignations = 0
            gpas = 0
            events = 0
            submissions = 0
            task_completions = 0
            trainings = 0

            evt_types = list(ScoreType.objects.filter(type="Evt"))
            sub_types = list(ScoreType.objects.filter(type="Sub"))
            badges = list(Badge.objects.all()[:5]) or [self._make_badge()]
            guards = list(Guard.objects.all()[:5]) or [self._make_guard()]
            task_dates = self._ensure_task_dates(activity_start, activity_end)

            for chapter in chapters:
                chapter_users, chapter_stats = self._populate_chapter(
                    chapter,
                    ay_start=ay_start,
                    ay_end=ay_end,
                    activity_start=activity_start,
                    activity_end=activity_end,
                    today=today,
                    users_per_chapter=opts["users_per_chapter"],
                    events_per_chapter=opts["events_per_chapter"],
                    submissions_per_chapter=opts["submissions_per_chapter"],
                    tasks_per_chapter=opts["tasks_per_chapter"],
                    trainings_per_user=opts["trainings_per_user"],
                    evt_types=evt_types,
                    sub_types=sub_types,
                    badges=badges,
                    guards=guards,
                    task_dates=task_dates,
                )
                users_created += len(chapter_users)
                initiations += chapter_stats["initiations"]
                depledges += chapter_stats["depledges"]
                prealums += chapter_stats["prealums"]
                resignations += chapter_stats["resignations"]
                gpas += chapter_stats["gpas"]
                events += chapter_stats["events"]
                submissions += chapter_stats["submissions"]
                task_completions += chapter_stats["task_completions"]
                trainings += chapter_stats["trainings"]

        self.stdout.write(self.style.SUCCESS("\nSeed complete."))
        self._print_row("Regions", len(regions))
        self._print_row("Chapters", len(chapters))
        self._print_row("Users", users_created)
        self._print_row("Initiations (AY)", initiations)
        self._print_row("Depledges (AY)", depledges)
        self._print_row("Prealumni (AY, approved)", prealums)
        self._print_row("Resignations (AY, approved)", resignations)
        self._print_row("UserSemesterGPA rows", gpas)
        self._print_row("Events (AY)", events)
        self._print_row("Submissions (AY)", submissions)
        self._print_row("Task completions (AY)", task_completions)
        self._print_row("Trainings (AY)", trainings)

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def _reset_seed_data(self):
        self.stdout.write(self.style.WARNING("Deleting existing seed data…"))
        seed_users = User.objects.filter(email__endswith=f"@{SEED_EMAIL_DOMAIN}")
        seed_chapters = Chapter.objects.filter(school__startswith=SEED_SCHOOL_PREFIX)
        seed_regions = Region.objects.filter(name__startswith=SEED_REGION_PREFIX)
        seed_task_dates = TaskDate.objects.filter(task__name__startswith=SEED_TASK_PREFIX)

        # Order matters — child rows first.
        Training.objects.filter(user__in=seed_users).delete()
        TaskChapter.objects.filter(chapter__in=seed_chapters).delete()
        seed_task_dates.delete()
        Task.objects.filter(name__startswith=SEED_TASK_PREFIX).delete()
        Submission.objects.filter(chapter__in=seed_chapters).delete()
        Event.objects.filter(chapter__in=seed_chapters).delete()
        ResignationProcess.objects.filter(chapter__in=seed_chapters).delete()
        PrematureAlumnus.objects.filter(user__in=seed_users).delete()
        Depledge.objects.filter(user__in=seed_users).delete()
        Initiation.objects.filter(user__in=seed_users).delete()
        UserSemesterGPA.objects.filter(user__in=seed_users).delete()
        UserStatusChange.objects.filter(user__in=seed_users).delete()
        seed_users.delete()
        ChapterCurricula.objects.filter(chapter__in=seed_chapters).delete()
        seed_chapters.delete()
        seed_regions.delete()

    # ------------------------------------------------------------------
    # Region / Chapter / User factories
    # ------------------------------------------------------------------

    def _create_regions(self, count):
        regions = []
        for name in REGION_NAMES[:count]:
            region, _ = Region.objects.get_or_create(
                name=f"{SEED_REGION_PREFIX}{name}",
                defaults={
                    "email": f"{name.lower().replace(' ', '-')}@{SEED_EMAIL_DOMAIN}",
                    "website": f"https://{name.lower().replace(' ', '-')}.example.com",
                    "facebook": f"https://facebook.com/tt-{name.lower().replace(' ', '-')}",
                },
            )
            regions.append(region)
        return regions

    def _create_chapters(self, regions, chapters_per_region):
        chapters = []
        # Round-robin chapter names across regions so `Alpha Chapter of Northeast`,
        # `Beta Chapter of Southeast`, etc.
        idx = 0
        for region in regions:
            for _ in range(chapters_per_region):
                root = CHAPTER_ROOTS[idx % len(CHAPTER_ROOTS)]
                idx += 1
                chapter_name = f"{root} {region.name.replace(SEED_REGION_PREFIX, '')}"
                school_name = f"{SEED_SCHOOL_PREFIX}{chapter_name} University"
                chapter, created = Chapter.objects.get_or_create(
                    name=chapter_name,
                    defaults={
                        "region": region,
                        "email": f"{root.lower()}-{region.name.lower().replace(' ', '-')}@{SEED_EMAIL_DOMAIN}",
                        "school": school_name,
                        "school_type": random.choice(["semester", "quarter"]),
                        "address_contact": f"{root} Chapter House Mgr",
                        "address_phone_number": "5125550000",
                        "council": "IFC" if random.random() < 0.7 else "PFC",
                        "candidate_chapter": random.random() < 0.15,
                        "active": True,
                        "greek": root[:2].lower(),
                    },
                )
                if created:
                    ChapterCurricula.objects.bulk_create(
                        [ChapterCurricula(chapter=chapter, major=major) for major in random.sample(MAJORS, 5)]
                    )
                else:
                    # Ensure region matches even for pre-existing seed chapters.
                    if chapter.region_id != region.id:
                        chapter.region = region
                        chapter.save(update_fields=["region"])
                chapters.append(chapter)
        return chapters

    # ------------------------------------------------------------------
    # Chapter population
    # ------------------------------------------------------------------

    def _populate_chapter(
        self,
        chapter,
        *,
        ay_start,
        ay_end,
        activity_start,
        activity_end,
        today,
        users_per_chapter,
        events_per_chapter,
        submissions_per_chapter,
        tasks_per_chapter,
        trainings_per_user,
        evt_types,
        sub_types,
        badges,
        guards,
        task_dates,
    ):
        # Give each chapter its own size so bar charts have visual variance
        # instead of every bar landing at the same height.
        chapter_users = _jitter(users_per_chapter, spread=0.30, floor=5)
        # Status-mix percentages also get a small nudge per chapter so no two
        # chapters land on identical PNM / initiation / retention numbers.
        pct_active = max(0.30, min(0.80, random.gauss(0.60, 0.06)))
        pct_pnm = max(0.05, min(0.25, random.gauss(0.15, 0.04)))
        pct_depledge = max(0.0, min(0.15, random.gauss(0.05, 0.02)))
        pct_prealum = max(0.0, min(0.15, random.gauss(0.05, 0.02)))
        pct_resignation = max(0.0, min(0.15, random.gauss(0.05, 0.02)))
        mix = {
            "active": int(chapter_users * pct_active),
            "pnm": int(chapter_users * pct_pnm),
            "depledge": int(chapter_users * pct_depledge),
            "prealum": int(chapter_users * pct_prealum),
            "resignation": int(chapter_users * pct_resignation),
        }
        mix["alumni"] = max(0, chapter_users - sum(mix.values()))
        stats = {
            "initiations": 0,
            "depledges": 0,
            "prealums": 0,
            "resignations": 0,
            "gpas": 0,
            "events": 0,
            "submissions": 0,
            "task_completions": 0,
            "trainings": 0,
        }
        users = []
        curricula = list(chapter.curricula.all())
        badge = random.choice(badges)
        guard = random.choice(guards)

        for status_kind, n in mix.items():
            for _ in range(n):
                user = self._make_user(chapter, curricula)
                users.append(user)

                if status_kind == "active":
                    # Backfill 1–4 years of history so the chapter dashboard's
                    # composition graph has multiple year-terms of data to draw.
                    active_years_ago = random.uniform(1.0, 4.0)
                    pnm_start = today - datetime.timedelta(days=int(active_years_ago * 365) + 45)
                    init_date = today - datetime.timedelta(days=int(active_years_ago * 365))
                    self._set_status(user, "pnm", start=pnm_start)
                    self._make_initiation(user, chapter, date=init_date, badge=badge, guard=guard)
                    self._set_status(user, "active", start=init_date)
                    # Some active users have prior semester GPA history so the
                    # GPA line graph isn't a single-point spike.
                    self._backfill_gpa_history(user, init_date, today)
                elif status_kind == "pnm":
                    start = _random_date_in_range(ay_start, ay_end)
                    self._set_status(user, "pnm", start=start)
                    # Roughly half of PNMs get initiated later in the AY.
                    if random.random() < 0.5:
                        init_min = start + datetime.timedelta(days=30)
                        init_max = ay_end.date()
                        if init_min < init_max:
                            init_date = init_min + datetime.timedelta(
                                days=random.randint(0, (init_max - init_min).days)
                            )
                            self._make_initiation(user, chapter, date=init_date, badge=badge, guard=guard)
                            stats["initiations"] += 1
                            self._set_status(user, "active", start=init_date)
                elif status_kind == "depledge":
                    pnm_start = _random_date_in_range(ay_start, ay_end)
                    self._set_status(user, "pnm", start=pnm_start)
                    dep_min = pnm_start + datetime.timedelta(days=7)
                    dep_max = ay_end.date()
                    if dep_min < dep_max:
                        dep_date = dep_min + datetime.timedelta(days=random.randint(0, (dep_max - dep_min).days))
                        Depledge.objects.create(
                            user=user,
                            reason=random.choice([r.value[0] for r in Depledge.REASONS]),
                            date=dep_date,
                        )
                        stats["depledges"] += 1
                elif status_kind == "prealum":
                    # Prealum flow: initiated earlier, granted prealum this AY.
                    init_date = ay_start.date() - datetime.timedelta(days=random.randint(180, 720))
                    self._make_initiation(user, chapter, date=init_date, badge=badge, guard=guard)
                    self._set_status(user, "active", start=init_date)
                    finished_dt = _dt(_random_date_in_range(ay_start, ay_end))
                    PrematureAlumnus.objects.create(
                        user=user,
                        approved_exec=True,
                        finished=finished_dt,
                        good_standing=True,
                        financial=True,
                        semesters=True,
                        lifestyle=True,
                        consideration=True,
                        vote=True,
                        prealumn_type="less4",
                        exec_comments="Approved, seed data",
                        form=ContentFile(b"seed", name=f"prealum_{uuid.uuid4().hex[:6]}.pdf"),
                    )
                    stats["prealums"] += 1
                elif status_kind == "resignation":
                    init_date = ay_start.date() - datetime.timedelta(days=random.randint(90, 540))
                    self._make_initiation(user, chapter, date=init_date, badge=badge, guard=guard)
                    self._set_status(user, "active", start=init_date)
                    finished_dt = _dt(_random_date_in_range(ay_start, ay_end))
                    # ResignationProcess requires two officer FKs — reuse this user's chapter's actives.
                    officer1 = self._get_or_make_officer_user(chapter, curricula)
                    officer2 = self._get_or_make_officer_user(chapter, curricula)
                    ResignationProcess.objects.create(
                        user=user,
                        chapter=chapter,
                        approved_exec=True,
                        finished=finished_dt,
                        resign=True,
                        secrets=True,
                        expel=True,
                        return_evidence=True,
                        obligation=True,
                        fee=True,
                        signature=user.name or "Seed User",
                        good_standing=True,
                        returned=True,
                        financial=True,
                        fee_paid=True,
                        officer1=officer1,
                        officer2=officer2,
                        signature_o1=officer1.name or "Officer One",
                        signature_o2=officer2.name or "Officer Two",
                        approved_o1=True,
                        approved_o2=True,
                        letter=ContentFile(b"seed", name=f"resign_{uuid.uuid4().hex[:6]}.pdf"),
                        exec_comments="Approved, seed data",
                    )
                    stats["resignations"] += 1
                elif status_kind == "alumni":
                    init_date = ay_start.date() - datetime.timedelta(days=random.randint(730, 3000))
                    self._make_initiation(user, chapter, date=init_date, badge=badge, guard=guard)
                    # Graduated 6mo–2y ago so the row is definitely current.
                    alum_start = today - datetime.timedelta(days=random.randint(180, 730))
                    self._set_status(user, "alumni", start=alum_start)

                # Everyone with an initiation this AY (or earlier) gets a GPA row.
                if random.random() < 0.5:
                    UserSemesterGPA.objects.create(
                        user=user,
                        year=ay_start.year,
                        term=random.choice(["fa", "sp"]),
                        gpa=round(random.uniform(2.4, 4.0), 2),
                    )
                    stats["gpas"] += 1

        # Activity items (events / submissions / tasks / trainings) span the
        # full ~4-year activity window ending today. That way historical AYs
        # picked from the region dashboard's AY selector each land on real
        # data, and the /chapters/<slug>/activity/ page (which looks at the
        # PAST few months) has past events to render.
        activity_years = max(1.0, (activity_end - activity_start).days / 365.0)

        # Events for this chapter — scale by the number of activity years so
        # the *per-AY* density stays close to what `--events-per-chapter`
        # implies. Per-chapter jitter keeps bars visually varied.
        events_target = int(events_per_chapter * activity_years)
        chapter_events = _jitter(events_target, spread=0.40, floor=0)
        if evt_types and chapter_events:
            for _ in range(chapter_events):
                Event.objects.create(
                    name=f"{chapter.name} Event {uuid.uuid4().hex[:6]}",
                    date=_random_date_in_range(activity_start, activity_end),
                    type=random.choice(evt_types),
                    chapter=chapter,
                    description="Seeded event for dashboard QA.",
                    members=random.randint(5, 80),
                    alumni=random.randint(0, 20),
                    pledges=random.randint(0, 25),
                    guests=random.randint(0, 40),
                    duration=random.randint(30, 240),
                )
                stats["events"] += 1

        # Submissions.
        submissions_target = int(submissions_per_chapter * activity_years)
        chapter_submissions = _jitter(submissions_target, spread=0.40, floor=0)
        if sub_types and users and chapter_submissions:
            for _ in range(chapter_submissions):
                submitter = random.choice(users)
                Submission.objects.create(
                    user=submitter,
                    date=_random_date_in_range(activity_start, activity_end),
                    file=ContentFile(b"seed", name=f"sub_{uuid.uuid4().hex[:6]}.pdf"),
                    name=f"{chapter.name} Submission {uuid.uuid4().hex[:6]}",
                    type=random.choice(sub_types),
                    chapter=chapter,
                )
                stats["submissions"] += 1

        # Task completions — task_dates already span the activity window.
        chapter_task_dates = [td for td in task_dates if td.school_type in (chapter.school_type, "all")]
        tasks_target = int(tasks_per_chapter * activity_years)
        chapter_tasks = _jitter(tasks_target, spread=0.35, floor=0)
        if chapter_task_dates and chapter_tasks:
            k = min(chapter_tasks, len(chapter_task_dates))
            for td in random.sample(chapter_task_dates, k=k):
                obj, created = TaskChapter.objects.get_or_create(
                    task=td,
                    chapter=chapter,
                    date=td.date,
                )
                if created:
                    stats["task_completions"] += 1

        # Training completions for active users — only ~70% complete training
        # in a given AY, and among those the count varies. Trainings span the
        # full activity window.
        if trainings_per_user:
            trainings_target = max(1, int(trainings_per_user * activity_years))
            active_users = [u for u in users if u.current_status in ("active", "activepend", "activeCC")]
            for u in active_users:
                if random.random() > 0.7:
                    continue  # ~30% skip training
                user_trainings = _jitter(trainings_target, spread=0.5, floor=0)
                for _ in range(user_trainings):
                    Training.objects.create(
                        user=u,
                        progress_id=uuid.uuid4().hex,
                        course_id=random.choice(["safety-101", "hazing-prevention", "bystander-intervention"]),
                        course_title="Health & Safety Seed Course",
                        completed=True,
                        completed_time=_dt(_random_date_in_range(activity_start, activity_end)),
                        max_quiz_score=round(random.uniform(70, 100), 1),
                    )
                    stats["trainings"] += 1

        return users, stats

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_user(self, chapter, curricula):
        first = _faker.first_name()
        last = _faker.last_name()
        # Use a UUID slug rather than the name so uniqueness across chapters
        # is guaranteed even when Faker collides.
        email = f"{first.lower()}.{last.lower()}.{uuid.uuid4().hex[:8]}@{SEED_EMAIL_DOMAIN}"
        user = User(
            email=email,
            username=email,
            first_name=first,
            last_name=last,
            name=f"{first} {last}",
            chapter=chapter,
            graduation_year=random.randint(datetime.date.today().year - 1, datetime.date.today().year + 5),
            badge_number=random.randint(10_000_000, 99_999_999),
            major=random.choice(curricula) if curricula else None,
        )
        user.set_password("seedpassword")
        user.save()
        return user

    def _get_or_make_officer_user(self, chapter, curricula):
        officer = (
            User.objects.filter(
                chapter=chapter,
                email__endswith=f"@{SEED_EMAIL_DOMAIN}",
                current_status__in=["active", "activepend"],
            )
            .order_by("?")
            .first()
        )
        if officer:
            return officer
        # None yet — spin one up.
        officer = self._make_user(chapter, curricula)
        self._set_status(officer, "active", start=(datetime.date.today() - datetime.timedelta(days=90)))
        return officer

    def _set_status(self, user, status, *, start):
        """Create a UserStatusChange row starting `start` and running to year 2100.

        We bypass `User.set_current_status` because it re-queries and rewrites
        sibling rows on every call, which becomes an N^2 nightmare when seeding
        thousands of users. We close any previous open-ended rows manually and
        only bump `user.current_status` when the new row actually covers today.
        """
        today = datetime.date.today()
        # Close open-ended prior status rows so date ranges don't overlap.
        UserStatusChange.objects.filter(user=user, end__gte=start).update(end=start - datetime.timedelta(days=1))
        UserStatusChange.objects.create(
            user=user,
            status=status,
            start=start,
            end=datetime.date(2100, 1, 1),
        )
        if start <= today:
            user.current_status = status
            user.save(update_fields=["current_status"])

    def _make_initiation(self, user, chapter, *, date, badge, guard):
        if Initiation.objects.filter(user=user).exists():
            return
        init = Initiation(
            user=user,
            chapter=chapter,
            date=date,
            date_graduation=date + datetime.timedelta(days=1460),
            roll=random.randint(100_000, 999_999_999),
            gpa=round(random.uniform(2.5, 4.0), 2),
            test_a=random.randint(70, 100),
            test_b=random.randint(70, 100),
            badge=badge,
            guard=guard,
        )
        # `status_update=False` skips the automatic set_current_status side
        # effect — we manage user status explicitly in _populate_chapter.
        init.save(status_update=False)

    def _backfill_gpa_history(self, user, since_date, today):
        """Create one UserSemesterGPA per (Fall, Spring) semester between
        `since_date` and `today` so the chapter dashboard's GPA line has
        multi-term history to plot. Skips ~30% of semesters at random to
        avoid perfectly uniform coverage.
        """
        year, term = since_date.year, "fa" if since_date.month >= 7 else "sp"
        # `today` is a `date` — cap history there.
        end_year = today.year
        end_term = "fa" if today.month >= 7 else "sp"
        while (year, term) <= (end_year, end_term):
            if random.random() > 0.3:
                UserSemesterGPA.objects.create(
                    user=user,
                    year=year,
                    term=term,
                    gpa=round(random.uniform(2.4, 4.0), 2),
                )
            # Advance one semester.
            if term == "sp":
                term = "fa"
            else:
                term = "sp"
                year += 1

    def _ensure_task_dates(self, activity_start, activity_end):
        """Make sure there's a seeded Task with a spread of due dates covering
        the activity window (~4 years back to today) so each historical AY on
        the region dashboard has task-completion data.

        Uses `[SEED]`-prefixed Task names so `--reset` can clean them up.
        """
        base_task, _ = Task.objects.get_or_create(
            name=f"{SEED_TASK_PREFIX}Chapter Report",
            defaults=dict(
                owner="regent",
                type="task",
                resource="",
                description="Seed task for dashboard QA.",
            ),
        )
        # ~24 due dates across the window (roughly one every 2 months of the
        # 4-year span) so each AY has 6+ tasks to sample completions from.
        span = (activity_end.date() - activity_start.date()).days or 1
        n_slots = 24
        step = max(1, span // n_slots)
        dates = []
        for i in range(n_slots):
            due = activity_start.date() + datetime.timedelta(days=i * step)
            for school_type in ("semester", "quarter"):
                td, _ = TaskDate.objects.get_or_create(
                    task=base_task,
                    date=due,
                    school_type=school_type,
                )
                dates.append(td)
        return dates

    def _make_badge(self):
        return Badge.objects.create(
            name="Seed Badge",
            code="SEED",
            description="Seeded badge for dashboard QA.",
            cost=0,
        )

    def _make_guard(self):
        return Guard.objects.create(
            name="Seed Guard",
            code="SEEDG",
            letters=Guard.ONE_LETTER,
            description="Seeded guard for dashboard QA.",
            cost=0,
        )

    def _print_row(self, label, count):
        self.stdout.write(f"  {label:<32} {count}")
