"""Populate a QA environment so the whole guides feature can be walked through.

The catalog and Role Guides work off the registry, which ``dbseed``
already loads -- but the *time-sensitive* half of the feature does not show up on
a fresh database at all. Nothing has been released recently, so What's New is
empty, no `New` badge appears anywhere, and there is no acknowledgement history
to prove the "Got it" state actually persists.

This command manufactures exactly that missing state. Everything it creates is
prefixed ``[DEMO]`` and is removable with ``--flush``, so it can be run against a
staging copy of production data without leaving anything ambiguous behind.

See docs/specs/guides-qa.md for the walkthrough this seeds.
"""

import random
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction
from django.utils import timezone

from core.seed_guard import ensure_seeding_allowed
from thetatauCMT.announcements.models import Announcement
from thetatauCMT.guides.models import Audience, Feature, FeatureArea, UserAcknowledgement
from thetatauCMT.users.models import User

DEMO = "[DEMO] "

ANNOUNCEMENTS = [
    {
        "title": f"{DEMO}Everyone sees this one",
        "content": "<p>A plain announcement, visible to every signed-in member and dismissible.</p>",
        "audience": Audience.MEMBER,
        "roles": [],
        "dismissible": True,
        "priority": 3,
    },
    {
        "title": f"{DEMO}Officers only",
        "content": "<p>Only chapter officers and above should see this.</p>",
        "audience": Audience.OFFICER,
        "roles": [],
        "dismissible": True,
        "priority": 4,
    },
    {
        "title": f"{DEMO}Treasurers only",
        "content": "<p>Role-targeted: only a Treasurer should see this, whatever their audience.</p>",
        "audience": Audience.MEMBER,
        "roles": ["treasurer"],
        "dismissible": True,
        "priority": 5,
    },
    {
        "title": f"{DEMO}Pinned compliance notice",
        "content": "<p>Not dismissible. There should be no &ldquo;Got it&rdquo; button on this one.</p>",
        "audience": Audience.MEMBER,
        "roles": [],
        "dismissible": False,
        "priority": 1,
    },
]


class Command(BaseCommand):
    help = "Seed demo announcements, a freshly released feature, and acknowledgement history."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing [DEMO] guides data before seeding. Touches nothing else.",
        )
        parser.add_argument("--seed", type=int, default=None, help="Seed the RNG for reproducible output.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Required when DEBUG is off. Without it the command refuses to run.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        ensure_seeding_allowed(options["force"])
        if options["seed"] is not None:
            random.seed(options["seed"])

        if options["flush"]:
            self._flush()

        # The demo feature has to hang off a real area, so make sure the registry
        # is there. The loader is idempotent, so this is free on a seeded database.
        call_command("load_feature_registry", verbosity=0)

        feature = self._released_feature()
        self._announcements(feature)
        self._personas(feature)
        self._role_holders()
        self.stdout.write(self.style.SUCCESS("Guides demo data seeded. See docs/specs/guides-qa.md."))

    # -- steps -----------------------------------------------------------

    def _flush(self):
        announcements = Announcement.objects.filter(title__startswith=DEMO)
        features = Feature.objects.filter(key__startswith="demo-")
        # Acknowledgements hang off a generic key, so nothing cascades -- forget
        # them explicitly before the targets go, or they become orphan rows.
        removed_ack = self._forget(announcements) + self._forget(features)
        removed_ann, _ = announcements.delete()
        removed_feat, _ = features.delete()
        self.stdout.write(
            f"  flushed {removed_ann} announcements, {removed_feat} features, {removed_ack} acknowledgements"
        )

    @staticmethod
    def _forget(queryset):
        ids = list(queryset.values_list("pk", flat=True))
        if not ids:
            return 0
        removed, _ = UserAcknowledgement.objects.filter(
            content_type=ContentType.objects.get_for_model(queryset.model),
            object_id__in=ids,
        ).delete()
        return removed

    def _released_feature(self):
        """A feature released today, so What's New and the `New` badge have something to show."""
        area = FeatureArea.objects.active().filter(key="getting-started").first()
        if area is None:
            area = FeatureArea.objects.active().first()
        if area is None:
            raise CommandError("No feature areas exist. Run load_feature_registry first.")
        feature, _ = Feature.objects.update_or_create(
            key="demo-brand-new-thing",
            defaults={
                "area": area,
                "name": f"{DEMO}A brand new thing",
                "short_description": "Released today, so it should appear in What's New with a New badge.",
                "long_description": "Acknowledging it in the modal should also clear the badge in the catalog.",
                "url_name": "guides:catalog",
                "audience": Audience.MEMBER,
                "released_at": timezone.now().date(),
                "release_version": "demo",
                "order": 999,
                "is_active": True,
            },
        )
        self.stdout.write(f"  released feature: {feature.key}")
        return feature

    def _announcements(self, feature):
        now = timezone.now()
        created = 0
        for index, spec in enumerate(ANNOUNCEMENTS):
            _, was_created = Announcement.objects.update_or_create(
                title=spec["title"],
                defaults={
                    **spec,
                    "publish_start": now - timedelta(days=1),
                    "publish_end": now + timedelta(days=30),
                    # Wiring one announcement to the demo feature gives the What's
                    # New card a link to follow.
                    "feature": feature if index == 0 else None,
                },
            )
            created += int(was_created)
        self.stdout.write(f"  announcements: {created} added, {len(ANNOUNCEMENTS) - created} refreshed")

    def _personas(self, feature):
        """Three accounts at different stages, so every "seen" state is reachable.

        The QA script needs a user who has seen nothing (the What's New modal
        fires), one who has seen everything (it must not fire), and one part-way
        through (some badges cleared, some not). Those states only exist as
        history rows, so they cannot be seeded by fixture.
        """
        candidates = list(User.objects.filter(is_active=True).order_by("?")[:3])
        if len(candidates) < 3:
            self.stdout.write(self.style.WARNING("  fewer than 3 users -- skipping persona history"))
            return
        fresh, caught_up, midway = candidates
        announcements = list(Announcement.objects.filter(title__startswith=DEMO))

        self._clear(fresh)
        self._acknowledge(caught_up, announcements, Feature.objects.active())

        self._clear(midway)
        self._acknowledge(midway, announcements[:1], Feature.objects.filter(pk=feature.pk))

        self.stdout.write("  personas:")
        self.stdout.write(f"    seen nothing:     {fresh.username}")
        self.stdout.write(f"    seen everything:  {caught_up.username}")
        self.stdout.write(f"    part-way through: {midway.username}")

    def _role_holders(self):
        """Report who currently holds each duty role, rather than inventing officers.

        Manufacturing ``UserRoleChange`` rows would fire the officer email signals
        and rewrite real people's offices on a staging copy. Reporting existing
        holders gets QA the same coverage with none of that risk.
        """
        self.stdout.write("  log in as, to check role targeting:")
        for role in ["regent", "treasurer", "risk management chair", "adviser", "regional director"]:
            holder = User.objects.filter(is_active=True, current_roles__contains=[role]).order_by("?").first()
            shown = holder.username if holder else self.style.WARNING("none in this database")
            self.stdout.write(f"    {role:<22} {shown}")
        plain = (
            User.objects.filter(is_active=True)
            .filter(models.Q(current_roles__isnull=True) | models.Q(current_roles=[]))
            .order_by("?")
            .first()
        )
        self.stdout.write(f"    {'plain member':<22} {plain.username if plain else 'none in this database'}")

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _clear(user):
        UserAcknowledgement.objects.filter(user=user).delete()

    @staticmethod
    def _acknowledge(user, announcements, features):
        for target, content_type in [
            (announcements, ContentType.objects.get_for_model(Announcement)),
            (features, ContentType.objects.get_for_model(Feature)),
        ]:
            for obj in target:
                UserAcknowledgement.objects.update_or_create(
                    user=user,
                    content_type=content_type,
                    object_id=obj.pk,
                    defaults={"source": UserAcknowledgement.Source.MODAL},
                )
