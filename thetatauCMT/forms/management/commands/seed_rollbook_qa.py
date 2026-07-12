"""Seed candidate chapters + prospective new members (PNMs) for Roll Book QA.

The Roll Book process (Forms → Initiation/Depledge selection → "Roll") renders a
membership-roll PDF for each selected pledge.  Candidate chapters use their own
roll template, so QA needs (a) candidate chapters and (b) pledges/PNMs sitting in
them, plus a login-able officer to drive the flow.

This command is **idempotent** and only ever touches its own seed rows:

- Users are tagged by the email suffix ``@rollbook-qa.thetatau.local``.
- Chapters are named ``[QA] Candidate Chapter N`` (``candidate_chapter=True``)
  with school ``[QA] Candidate School N`` and live in the ``[QA] Candidate
  Region`` region.

For each candidate chapter it ensures:

- a login-able **regent** (officer group + current role + active status + a
  Risk-Management form signed this semester, so the RMP middleware does not
  bounce them), and
- N **PNMs** (``UserStatusChange`` status ``pnm`` covering today, so
  ``Chapter.pledges()`` returns them) with a home address, major, birth date
  and graduation year — the fields the roll page prints.

Usage::

    podman exec thetataucmt_local_django python manage.py seed_rollbook_qa
    podman exec thetataucmt_local_django python manage.py seed_rollbook_qa --chapters 3 --pnms 8
    podman exec thetataucmt_local_django python manage.py seed_rollbook_qa --password hunter2
    podman exec thetataucmt_local_django python manage.py seed_rollbook_qa --reset
"""

from __future__ import annotations

import datetime
import re

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import ProtectedError

from core.address import get_or_create_address
from thetatauCMT.chapters.models import Chapter, ChapterCurricula
from thetatauCMT.forms.models import RiskManagement
from thetatauCMT.regions.models import Region
from thetatauCMT.users.models import User, UserRoleChange, UserStatusChange

SEED_EMAIL_DOMAIN = "rollbook-qa.thetatau.local"
SEED_SCHOOL_DOMAIN = "rollbook-qa.edu"
SEED_CHAPTER_PREFIX = "[QA] Candidate Chapter"
SEED_SCHOOL_PREFIX = "[QA] Candidate School"
SEED_REGION_NAME = "[QA] Candidate Region"
DEFAULT_PASSWORD = "rollbookqa"
OFFICER_ROLE = "regent"

_FOREVER = datetime.date(2100, 1, 1)

_FIRST_NAMES = [
    "Amara",
    "Beto",
    "Chandra",
    "Diego",
    "Esi",
    "Farid",
    "Greta",
    "Hassan",
    "Imani",
    "Jae",
    "Katya",
    "Liam",
    "Mei",
    "Nikhil",
    "Olga",
    "Pedro",
    "Qiana",
    "Rafael",
    "Sofia",
    "Tariq",
    "Uma",
    "Viktor",
    "Wren",
    "Ximena",
]
_LAST_NAMES = [
    "Abara",
    "Bianchi",
    "Costa",
    "Dawson",
    "Eng",
    "Fischer",
    "Gupta",
    "Haddad",
    "Ibarra",
    "Jensen",
    "Kaur",
    "Lozano",
    "Mbeki",
    "Novak",
    "Ortiz",
    "Petrov",
    "Quintero",
    "Reyes",
    "Sato",
    "Tran",
    "Underwood",
    "Vega",
    "Walsh",
    "Xu",
]
_MAJORS = [
    "Mechanical Engineering",
    "Electrical Engineering",
    "Civil Engineering",
    "Computer Science",
    "Chemical Engineering",
    "Biomedical Engineering",
]
# (street, city, state, state_code, postal_code)
_ADDRESSES = [
    ("100 Maple Avenue", "Columbus", "Ohio", "OH", "43201"),
    ("221 Baker Street", "Austin", "Texas", "TX", "78701"),
    ("55 Birch Lane", "Seattle", "Washington", "WA", "98101"),
    ("742 Evergreen Terrace", "Springfield", "Illinois", "IL", "62704"),
    ("9 Cedar Court", "Atlanta", "Georgia", "GA", "30301"),
    ("1600 Willow Way", "Denver", "Colorado", "CO", "80202"),
    ("48 Sycamore Street", "Boston", "Massachusetts", "MA", "02108"),
    ("3110 Aspen Drive", "Phoenix", "Arizona", "AZ", "85001"),
]

_slug_re = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _slug_re.sub("-", (value or "").lower()).strip("-")


def _pick(pool: list, seed: int):
    return pool[seed % len(pool)]


class Command(BaseCommand):
    help = "Idempotently seed candidate chapters + PNMs (pledges) for Roll Book QA."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--chapters",
            type=int,
            default=2,
            help="Number of candidate chapters to seed (default 2).",
        )
        parser.add_argument(
            "--pnms",
            type=int,
            default=6,
            help="Prospective new members per candidate chapter (default 6).",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for the seeded officer logins (default '{DEFAULT_PASSWORD}').",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously-seeded Roll Book QA rows before seeding.",
        )

    # ------------------------------------------------------------------ entry
    @transaction.atomic
    def handle(self, *args, **options) -> None:  # noqa: ANN401
        num_chapters = max(1, options["chapters"])
        num_pnms = max(1, options["pnms"])
        password = options["password"]
        stats = {"chapters": 0, "officers": 0, "pnms": 0}

        if options["reset"]:
            self._reset()

        region = self._ensure_region()
        officers: list[tuple[Chapter, User]] = []
        for index in range(1, num_chapters + 1):
            chapter = self._ensure_chapter(region, index)
            stats["chapters"] += 1
            majors = self._ensure_majors(chapter)
            officer = self._ensure_officer(chapter, index, password, stats)
            officers.append((chapter, officer))
            for pnm_index in range(1, num_pnms + 1):
                self._ensure_pnm(chapter, index, pnm_index, majors, stats)

        self._report(officers, num_pnms, password, stats)

    # ------------------------------------------------------------------ reset
    def _reset(self) -> None:
        self.stdout.write(self.style.WARNING("Resetting existing Roll Book QA seed data…"))
        deleted_users, _ = User.objects.filter(email__endswith=f"@{SEED_EMAIL_DOMAIN}").delete()
        self.stdout.write(f"  removed {deleted_users} seed user row(s)")
        qa_chapters = Chapter.objects.filter(
            candidate_chapter=True,
            name__startswith=SEED_CHAPTER_PREFIX,
            school__startswith=SEED_SCHOOL_PREFIX,
        )
        for chapter in qa_chapters:
            try:
                chapter.delete()
            except ProtectedError:
                # Something references the chapter (scores/tasks) — leave it in
                # place; it will be reused on the next run.
                self.stdout.write(self.style.NOTICE(f"  kept protected chapter {chapter.name}"))
        region = Region.objects.filter(name=SEED_REGION_NAME).first()
        if region and not region.chapters.exists():
            region.delete()

    # ---------------------------------------------------------------- region
    def _ensure_region(self) -> Region:
        region, _ = Region.objects.get_or_create(name=SEED_REGION_NAME)
        return region

    # --------------------------------------------------------------- chapter
    def _ensure_chapter(self, region: Region, index: int) -> Chapter:
        name = f"{SEED_CHAPTER_PREFIX} {index}"
        chapter, created = Chapter.objects.get_or_create(
            name=name,
            defaults={
                "region": region,
                "school": f"{SEED_SCHOOL_PREFIX} {index}",
                "candidate_chapter": True,
                "greek": f"QA{index}",
                "active": True,
            },
        )
        changed = []
        if not chapter.candidate_chapter:
            chapter.candidate_chapter = True
            changed.append("candidate_chapter")
        if not chapter.active:
            chapter.active = True
            changed.append("active")
        if chapter.region_id != region.pk:
            chapter.region = region
            changed.append("region")
        if changed:
            chapter.save(update_fields=changed)
        return chapter

    # ---------------------------------------------------------------- majors
    def _ensure_majors(self, chapter: Chapter) -> list[ChapterCurricula]:
        majors = []
        for major_name in _MAJORS:
            major, _ = ChapterCurricula.objects.get_or_create(
                chapter=chapter,
                major=major_name,
                defaults={"approved": True},
            )
            if not major.approved:
                major.approved = True
                major.save(update_fields=["approved"])
            majors.append(major)
        return majors

    # --------------------------------------------------------------- officer
    def _ensure_officer(self, chapter: Chapter, index: int, password: str, stats: dict) -> User:
        email = f"{OFFICER_ROLE}{index}@{SEED_EMAIL_DOMAIN}"
        first_name = _pick(_FIRST_NAMES, index)
        last_name = _pick(_LAST_NAMES, index + 7)
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "name": f"{first_name} {last_name}",
                "email_school": f"{OFFICER_ROLE}{index}@{_slug(chapter.name)}.{SEED_SCHOOL_DOMAIN}",
                "chapter": chapter,
                "badge_number": 950_000_000 + index,
                "graduation_year": 2026,
            },
        )
        if user.chapter_id != chapter.pk:
            user.chapter = chapter
            user.save(update_fields=["chapter"])
        # Always (re)set the password so QA always knows the credentials.
        user.set_password(password)
        user.save(update_fields=["password"])
        self._ensure_address(user, index)
        self._ensure_active_status(user, chapter)
        self._ensure_role(user, OFFICER_ROLE)
        off_group, _ = Group.objects.get_or_create(name="officer")
        off_group.user_set.add(user)
        self._ensure_rmp(user)
        if created:
            stats["officers"] += 1
        return user

    # ------------------------------------------------------------------ pnm
    def _ensure_pnm(self, chapter: Chapter, chapter_index: int, pnm_index: int, majors: list, stats: dict) -> User:
        email = f"pnm{chapter_index}-{pnm_index}@{SEED_EMAIL_DOMAIN}"
        seed = chapter_index * 31 + pnm_index
        first_name = _pick(_FIRST_NAMES, seed)
        last_name = _pick(_LAST_NAMES, seed + 3)
        major = _pick(majors, seed)
        birth_year = 2004 + (pnm_index % 4)
        user, created = User.objects.get_or_create(
            username=email,
            defaults={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "name": f"{first_name} {last_name}",
                "email_school": f"pnm{chapter_index}-{pnm_index}@{_slug(chapter.name)}.{SEED_SCHOOL_DOMAIN}",
                "chapter": chapter,
                "major": major,
                "badge_number": 960_000_000 + chapter_index * 1000 + pnm_index,
                "birth_date": datetime.date(birth_year, 1 + (pnm_index % 12), 1 + (pnm_index % 27)),
                "graduation_year": 2027 + (pnm_index % 3),
                "phone_number": f"512555{(1000 + seed) % 10000:04d}",
            },
        )
        changed = []
        if user.chapter_id != chapter.pk:
            user.chapter = chapter
            changed.append("chapter")
        if user.major_id != major.pk:
            user.major = major
            changed.append("major")
        if changed:
            user.save(update_fields=changed)
        self._ensure_address(user, seed)
        self._ensure_pnm_status(user)
        if created:
            stats["pnms"] += 1
        return user

    # -------------------------------------------------------------- helpers
    def _ensure_address(self, user: User, seed: int) -> None:
        if user.address_id:
            return
        street, city, state, state_code, postal = _pick(_ADDRESSES, seed)
        address = get_or_create_address(
            street=street,
            city=city,
            state=state,
            postal_code=postal,
            country="United States",
            state_code=state_code,
        )
        if address is not None:
            user.address = address
            user.save(update_fields=["address"])

    def _ensure_pnm_status(self, user: User) -> None:
        today = datetime.date.today()
        has_current_pnm = UserStatusChange.objects.filter(
            user=user, status="pnm", start__lte=today, end__gte=today
        ).exists()
        if has_current_pnm:
            return
        UserStatusChange.objects.create(
            user=user,
            status="pnm",
            start=today - datetime.timedelta(days=7),
            end=_FOREVER,
        )

    def _ensure_active_status(self, user: User, chapter: Chapter) -> None:
        today = datetime.date.today()
        status = "activeCC" if chapter.candidate_chapter else "active"
        if UserStatusChange.objects.filter(user=user, status=status, end__gte=today).exists():
            return
        UserStatusChange.objects.create(
            user=user,
            status=status,
            start=today - datetime.timedelta(days=7),
            end=_FOREVER,
        )

    def _ensure_role(self, user: User, role: str) -> None:
        today = datetime.date.today()
        if UserRoleChange.objects.filter(user=user, role=role, end__gte=today).exists():
            return
        UserRoleChange.objects.create(
            user=user,
            role=role,
            start=today - datetime.timedelta(days=7),
            end=_FOREVER,
        )
        user.refresh_from_db()
        if not user.current_roles or role not in user.current_roles:
            current = list(user.current_roles or [])
            current.append(role)
            user.current_roles = current
            user.save(update_fields=["current_roles"])

    def _ensure_rmp(self, user: User) -> None:
        if RiskManagement.user_signed_this_semester(user):
            return
        boolean_fields = [
            "alcohol",
            "hosting",
            "monitoring",
            "member",
            "officer",
            "abusive",
            "hazing",
            "substances",
            "high_risk",
            "transportation",
            "property_management",
            "guns",
            "trademark",
            "social",
            "indemnification",
            "agreement",
            "electronic_agreement",
            "terms_agreement",
        ]
        RiskManagement.objects.create(
            user=user,
            role=OFFICER_ROLE,
            submission=None,
            date=datetime.date.today(),
            typed_name=user.name,
            **{field: True for field in boolean_fields},
        )

    # ---------------------------------------------------------------- report
    def _report(self, officers: list, num_pnms: int, password: str, stats: dict) -> None:
        self.stdout.write(self.style.SUCCESS("\nRoll Book QA seed complete."))
        self.stdout.write(
            f"  candidate chapters: {stats['chapters']} | "
            f"new officers: {stats['officers']} | new PNMs: {stats['pnms']} "
            f"(target {num_pnms} PNMs/chapter)"
        )
        self.stdout.write("\nLog in as any of these chapter officers to drive the Roll Book flow:")
        for chapter, officer in officers:
            self.stdout.write(self.style.NOTICE(f"  {chapter.name}: ") + f"{officer.email}  /  {password}")
        self.stdout.write(
            "\nThen go to Forms → Initiate/Depledge Members (url name 'forms:init_selection'),\n"
            "mark PNMs as 'Roll', and download the roll book pages.\n"
        )
        self.stdout.write(
            self.style.NOTICE(
                f"All seed users carry the email suffix '@{SEED_EMAIL_DOMAIN}'. " "Re-run with --reset to remove them."
            )
        )
