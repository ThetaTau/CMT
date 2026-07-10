"""Seed the database with National events that are pending review.

National events are org-wide (not tied to a chapter), always public, and are
normally auto-approved when a National Officer creates them. This command
creates demo National events that are deliberately left in the ``pending``
state so the National-Officer review queue (``events:pending``) has content to
exercise the approve / reject workflow.

Idempotent guardrails:
- Every seeded event's name starts with ``"[SEED] "``.
- ``--reset`` deletes ONLY events matching that marker, so real data is safe.

Usage:
    podman exec thetataucmt_local_django python manage.py seed_pending_national_events
    podman exec thetataucmt_local_django python manage.py seed_pending_national_events --count 8 --approved 3
    podman exec thetataucmt_local_django python manage.py seed_pending_national_events --reset
"""

import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from thetatauCMT.events.models import Event
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.models import User

SEED_PREFIX = "[SEED] "

EVENT_IDEAS = [
    "National Convention",
    "National Day of Service",
    "National Leadership Academy",
    "National PD Webinar",
    "National Founders Day",
    "National Networking Mixer",
    "National Alumni Reunion",
    "National DEI Summit",
    "National STEM Outreach Fair",
    "National Directors Retreat",
]

CHAPTER_EVENT_IDEAS = [
    "Chapter Fundraiser",
    "Chapter Career Fair",
    "Chapter Service Day",
    "Chapter Alumni Night",
    "Chapter Info Session",
    "Chapter Game Night",
]


class Command(BaseCommand):
    help = "Seed National events that are pending National Officer review (demo data)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=5,
            help="Number of pending National events to create (default: 5).",
        )
        parser.add_argument(
            "--approved",
            type=int,
            default=2,
            help="Number of already-approved National events to create for contrast (default: 2).",
        )
        parser.add_argument(
            "--chapter-pending",
            type=int,
            default=4,
            help="Number of chapter-created public events pending review to create (default: 4).",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete previously seeded ([SEED]) events before creating new ones.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        count = options["count"]
        approved = options["approved"]
        chapter_pending = options["chapter_pending"]

        if options["reset"]:
            deleted, _ = Event.objects.filter(name__startswith=SEED_PREFIX).delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} previously seeded event(s)."))

        score_type = ScoreType.objects.filter(type="Evt").first()
        if score_type is None:
            raise CommandError("No 'Evt' ScoreType found; load scoretypes fixtures first.")

        # Attribute the events to a National Officer when one exists (created_by
        # is otherwise auto-populated only inside a request context).
        national_officer = User.objects.filter(groups__name="natoff").order_by("pk").first()

        today = timezone.now().date()
        created_pending = self._create_events(
            count,
            score_type=score_type,
            national_officer=national_officer,
            approval_status=Event.ApprovalStatus.PENDING,
            base_date=today + datetime.timedelta(days=30),
        )
        created_approved = self._create_events(
            approved,
            score_type=score_type,
            national_officer=national_officer,
            approval_status=Event.ApprovalStatus.APPROVED,
            base_date=today + datetime.timedelta(days=60),
            reviewer=national_officer,
        )
        created_chapter = self._create_chapter_events(
            chapter_pending,
            score_type=score_type,
            base_date=today + datetime.timedelta(days=20),
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created_pending} pending National, {created_approved} approved National, and "
                f"{created_chapter} chapter public pending event(s). "
                "Pending events appear in the review queue at /events/pending/."
            )
        )

    def _create_events(self, n, *, score_type, national_officer, approval_status, base_date, reviewer=None):
        created = 0
        for i in range(n):
            idea = EVENT_IDEAS[i % len(EVENT_IDEAS)]
            year = base_date.year + (i // len(EVENT_IDEAS))
            name = f"{SEED_PREFIX}{idea} {year}"[:50]
            date = base_date + datetime.timedelta(days=i * 7)
            # National events are not tied to a chapter (chapter=None).
            if Event.objects.filter(name=name, date=date, chapter__isnull=True).exists():
                continue
            event = Event(
                name=name,
                date=date,
                type=score_type,
                chapter=None,
                description=f"{idea} — org-wide National event (seed data).",
                is_national=True,
                is_public=True,
                approval_status=approval_status,
                duration=2,
            )
            if national_officer is not None:
                event.created_by = national_officer
            if reviewer is not None and approval_status == Event.ApprovalStatus.APPROVED:
                event.reviewed_by = reviewer
                event.reviewed_at = timezone.now()
            # Skip scoring: National events have no chapter to score.
            event.save(calculate_score=False)
            created += 1
        return created

    def _create_chapter_events(self, n, *, score_type, base_date):
        """Create chapter-created public events pending review (one per active chapter)."""
        if n <= 0:
            return 0
        from thetatauCMT.chapters.models import Chapter

        chapters = list(Chapter.objects.filter(active=True).order_by("pk"))
        if not chapters:
            self.stdout.write(self.style.WARNING("No active chapters found; skipping chapter public events."))
            return 0
        created = 0
        for i in range(n):
            chapter = chapters[i % len(chapters)]
            idea = CHAPTER_EVENT_IDEAS[i % len(CHAPTER_EVENT_IDEAS)]
            name = f"{SEED_PREFIX}{idea} {chapter.name}"[:50]
            date = base_date + datetime.timedelta(days=i * 5)
            if Event.objects.filter(name=name, date=date, chapter=chapter).exists():
                continue
            officer = User.objects.filter(chapter=chapter, groups__name="officer").order_by("pk").first()
            event = Event(
                name=name,
                date=date,
                type=score_type,
                chapter=chapter,
                description=f"{idea} — chapter public event pending National Officer review (seed data).",
                is_public=True,
                is_national=False,
                approval_status=Event.ApprovalStatus.PENDING,
                duration=2,
            )
            if officer is not None:
                event.created_by = officer
            # Skip scoring so seed data does not disturb real chapter scores.
            event.save(calculate_score=False)
            created += 1
        return created
