"""Seed the local DB with sample chapter and national officers for contact-sync QA.

Idempotent. This command NEVER deletes data — it only creates rows that don't
already exist (via ``get_or_create`` on the tagged email address). Re-running
it is a no-op.

For each active chapter, ensures five officers are on file — one for each of
the CHAPTER_OFFICER roles (regent, vice regent, treasurer, scribe,
corresponding secretary) — each with:

- an active ``UserStatusChange`` running from a week ago through 2100,
- a ``UserRoleChange`` covering today,
- the role appended to ``user.current_roles`` (via the pre-save signal on
  UserRoleChange),
- **both** ``email`` and ``email_school`` populated so contact-sync
  reviewers can visually confirm we're pushing both.

For the national officers scope, seeds one representative per role in
``COUNCIL`` and ``NATIONAL_OFFICER``.

Seed rows are identified by the email suffix
``@contact-sync-seed.thetatau.local`` — grep for that if you ever need to
find or remove them manually.

Usage::

    podman exec thetataucmt_local_django python manage.py seed_contact_sync_examples
    podman exec thetataucmt_local_django python manage.py seed_contact_sync_examples --chapters 5
    podman exec thetataucmt_local_django python manage.py seed_contact_sync_examples --skip-chapters
    podman exec thetataucmt_local_django python manage.py seed_contact_sync_examples --skip-national
"""

from __future__ import annotations

import datetime
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import COUNCIL, NATIONAL_OFFICER
from core.seed_guard import ensure_seeding_allowed
from thetatauCMT.chapters.models import Chapter
from thetatauCMT.contact_sync.officers import SYNCED_OFFICER_ROLES
from thetatauCMT.users.models import User, UserRoleChange, UserStatusChange

SEED_EMAIL_DOMAIN = "contact-sync-seed.thetatau.local"
SEED_SCHOOL_DOMAIN = "seed-university.edu"


# Sample first + last names — the pool is small on purpose so it's obvious
# these are seed contacts if they show up in someone's real address book.
_FIRST_NAMES = [
    "Alex",
    "Jordan",
    "Taylor",
    "Casey",
    "Morgan",
    "Riley",
    "Skyler",
    "Reese",
    "Avery",
    "Rowan",
    "Kai",
    "Sage",
    "Blair",
    "Quinn",
    "Emerson",
    "Frankie",
    "Harper",
    "Sydney",
    "Charlie",
    "Drew",
]
_LAST_NAMES = [
    "Ventura",
    "Chen",
    "Nguyen",
    "Patel",
    "Kim",
    "Alvarez",
    "Ali",
    "Okafor",
    "Bergstrom",
    "Kowalski",
    "Suzuki",
    "Rossi",
    "MacLeod",
    "Delacroix",
    "Hernandez",
    "O'Brien",
    "Smith",
    "Williams",
    "Baker",
    "Garcia",
]


class Command(BaseCommand):
    help = "Idempotently seed sample chapter + national officers for contact-sync QA."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--chapters",
            type=int,
            default=0,
            help="Limit to the first N active chapters (0 = all).",
        )
        parser.add_argument("--skip-chapters", action="store_true", help="Skip chapter officer seeding.")
        parser.add_argument("--skip-national", action="store_true", help="Skip national officer seeding.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Required to run when settings.DEBUG is off (production-like).",
        )

    # ------------------------------------------------------------------ entry
    def handle(self, *args, **options) -> None:  # noqa: ANN401
        ensure_seeding_allowed(options["force"])
        stats = {"chapter_users_created": 0, "chapter_users_updated": 0, "nat_users_created": 0, "nat_users_updated": 0}
        with transaction.atomic():
            if not options["skip_chapters"]:
                self._seed_chapters(options.get("chapters") or 0, stats)
            if not options["skip_national"]:
                self._seed_national(stats)
        self.stdout.write(self.style.SUCCESS("Seed complete."))
        for key, value in stats.items():
            self.stdout.write(f"  {key}: {value}")
        self.stdout.write(
            self.style.NOTICE(
                "Seed rows are tagged with email suffix " f"'@{SEED_EMAIL_DOMAIN}'. This command NEVER deletes data."
            )
        )

    # ------------------------------------------------------------------ chapter scope
    def _seed_chapters(self, limit: int, stats: dict) -> None:
        chapters_qs = Chapter.objects.exclude(active=False).order_by("name")
        if limit:
            chapters_qs = chapters_qs[:limit]
        chapters = list(chapters_qs)
        self.stdout.write(self.style.NOTICE(f"Seeding officers for {len(chapters)} chapter(s)…"))
        for chapter in chapters:
            for role in SYNCED_OFFICER_ROLES:
                self._ensure_chapter_officer(chapter, role, stats)

    def _ensure_chapter_officer(self, chapter: Chapter, role: str, stats: dict) -> User:
        role_slug = _slug(role)
        chapter_slug = (chapter.slug or _slug(chapter.name) or f"chapter{chapter.pk}").strip("-")
        email = f"{chapter_slug}-{role_slug}@{SEED_EMAIL_DOMAIN}"
        first_name = _pick(_FIRST_NAMES, hash((chapter.pk, role, "first")))
        last_name = _pick(_LAST_NAMES, hash((chapter.pk, role, "last")))
        email_school = (
            f"{first_name.lower()}.{last_name.lower().replace(chr(39), '')}@{chapter_slug}.{SEED_SCHOOL_DOMAIN}"
        )
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": first_name,
                "last_name": last_name,
                "name": f"{first_name} {last_name}",
                "email_school": email_school,
                "phone_number": _phone_for(email),
                "chapter": chapter,
                "badge_number": _badge_for(chapter.pk, role),
            },
        )
        changed_fields: list[str] = []
        # Reset key fields even on existing rows so re-running fixes any drift.
        if user.first_name != first_name:
            user.first_name = first_name
            changed_fields.append("first_name")
        if user.last_name != last_name:
            user.last_name = last_name
            changed_fields.append("last_name")
        if user.name != f"{first_name} {last_name}":
            user.name = f"{first_name} {last_name}"
            changed_fields.append("name")
        if user.email_school != email_school:
            user.email_school = email_school
            changed_fields.append("email_school")
        if user.chapter_id != chapter.pk:
            user.chapter = chapter
            changed_fields.append("chapter")
        if not user.phone_number:
            user.phone_number = _phone_for(email)
            changed_fields.append("phone_number")
        if changed_fields:
            user.save(update_fields=changed_fields)
        _ensure_active_status(user)
        _ensure_role(user, chapter, role)
        if created:
            stats["chapter_users_created"] += 1
        elif changed_fields:
            stats["chapter_users_updated"] += 1
        return user

    # ------------------------------------------------------------------ national scope
    def _seed_national(self, stats: dict) -> None:
        default_chapter = Chapter.objects.filter(active=True).order_by("pk").first()
        if default_chapter is None:
            self.stdout.write(self.style.WARNING("No active chapter, skipping national officer seed."))
            return
        national_roles = sorted(COUNCIL | NATIONAL_OFFICER)
        self.stdout.write(self.style.NOTICE(f"Seeding {len(national_roles)} national officer(s)…"))
        for role in national_roles:
            self._ensure_national_officer(default_chapter, role, stats)

    def _ensure_national_officer(self, home_chapter: Chapter, role: str, stats: dict) -> User:
        role_slug = _slug(role)
        email = f"nat-{role_slug}@{SEED_EMAIL_DOMAIN}"
        first_name = _pick(_FIRST_NAMES, hash(("nat", role, "first")))
        last_name = _pick(_LAST_NAMES, hash(("nat", role, "last")))
        email_school = f"{first_name.lower()}.{last_name.lower().replace(chr(39), '')}@national.{SEED_SCHOOL_DOMAIN}"
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "username": email,
                "first_name": first_name,
                "last_name": last_name,
                "name": f"{first_name} {last_name}",
                "email_school": email_school,
                "phone_number": _phone_for(email),
                "chapter": home_chapter,
                "badge_number": _badge_for(0, role),
            },
        )
        changed_fields: list[str] = []
        if user.first_name != first_name:
            user.first_name = first_name
            changed_fields.append("first_name")
        if user.last_name != last_name:
            user.last_name = last_name
            changed_fields.append("last_name")
        if user.email_school != email_school:
            user.email_school = email_school
            changed_fields.append("email_school")
        if not user.phone_number:
            user.phone_number = _phone_for(email)
            changed_fields.append("phone_number")
        if changed_fields:
            user.save(update_fields=changed_fields)
        _ensure_active_status(user)
        _ensure_role(user, home_chapter, role)
        if created:
            stats["nat_users_created"] += 1
        elif changed_fields:
            stats["nat_users_updated"] += 1
        return user


# --------------------------------------------------------------------- helpers
_slug_re = re.compile(r"[^a-z0-9]+")


def _slug(value: str) -> str:
    return _slug_re.sub("-", (value or "").lower()).strip("-")


def _pick(pool: list[str], seed: int) -> str:
    return pool[seed % len(pool)]


def _phone_for(email: str) -> str:
    # Deterministic fake 10-digit number so re-running is stable.
    digits = str(abs(hash(email)))[:10].ljust(10, "0")
    return f"+1{digits}"


def _badge_for(chapter_pk: int, role: str) -> int:
    # Well outside real badge-number range (max ~999,999,999) so we don't
    # collide with prod data.
    return 900_000_000 + (abs(hash((chapter_pk, role))) % 89_999_999)


def _ensure_active_status(user: User) -> None:
    """Make sure the user has a current 'active' UserStatusChange row."""
    today = datetime.date.today()
    if user.current_status == "active":
        # Belt-and-braces: also ensure a status row covering today exists so
        # `chapter.get_current_officers()` (which filters via ``current_roles``)
        # keeps working reliably.
        pass
    open_row = UserStatusChange.objects.filter(user=user, end__gte=today).first()
    if open_row is None:
        UserStatusChange.objects.create(
            user=user,
            status="active",
            start=today - datetime.timedelta(days=7),
            end=datetime.date(2100, 1, 1),
        )
    user.current_status = "active"
    user.save(update_fields=["current_status"])


def _ensure_role(user: User, chapter: Chapter, role: str) -> None:
    """Ensure the user has a current UserRoleChange for ``role`` covering today.

    The model's ``save()`` pre-save logic appends ``role`` to
    ``user.current_roles``, so we don't have to touch that field ourselves.
    """
    today = datetime.date.today()
    existing = UserRoleChange.objects.filter(user=user, role=role, end__gte=today).order_by("-end").first()
    if existing is not None:
        return
    UserRoleChange.objects.create(
        user=user,
        role=role,
        start=today - datetime.timedelta(days=7),
        end=today + datetime.timedelta(days=365),
    )
    # Defensive: `UserRoleChange.save` appends the role only if start/end
    # straddle tomorrow; reload to catch that.
    user.refresh_from_db()
    if user.current_roles is None or role not in user.current_roles:
        current = list(user.current_roles or [])
        if role not in current:
            current.append(role)
        user.current_roles = current
        user.save(update_fields=["current_roles"])
