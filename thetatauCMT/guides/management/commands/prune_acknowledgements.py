"""Drops acknowledgement rows whose target no longer matters (TWI-6).

``UserAcknowledgement`` is the highest-volume table in the guides app -- one row
per user per announced item -- and nothing else ever deletes from it. A row is
prunable once the thing it points at can no longer appear in anyone's feed:

* the target is gone (a hard-deleted announcement leaves the generic key dangling);
* the announcement's publish window closed more than ``--days`` ago;
* the feature is deactivated, or was released more than ``--days`` ago and is
  therefore past the "new" window for everyone.

Deleting a row is safe by construction: the only thing it can do is re-show an
item, and every prunable row belongs to an item that is no longer shown.
"""

from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.utils import timezone

from thetatauCMT.announcements.models import Announcement
from thetatauCMT.guides.models import Feature, UserAcknowledgement


class Command(BaseCommand):
    help = "Prune UserAcknowledgement rows whose announcement or feature is long expired."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=365,
            help="Keep rows for items that expired within this many days (default 365).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting it.",
        )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=options["days"])
        doomed = set()

        for model_class, keep_ids in (
            (Announcement, self._announcements_to_keep(cutoff)),
            (Feature, self._features_to_keep(cutoff)),
        ):
            content_type = ContentType.objects.get_for_model(model_class)
            rows = UserAcknowledgement.objects.filter(content_type=content_type).exclude(object_id__in=keep_ids)
            doomed.update(rows.values_list("id", flat=True))

        # Content types other than the two supported kinds are orphans from an
        # earlier shape of this table; they can never be rendered, so they go too.
        supported = [
            ContentType.objects.get_for_model(Announcement).id,
            ContentType.objects.get_for_model(Feature).id,
        ]
        doomed.update(UserAcknowledgement.objects.exclude(content_type_id__in=supported).values_list("id", flat=True))

        if options["dry_run"]:
            self.stdout.write(f"Would delete {len(doomed)} acknowledgement rows.")
            return
        deleted, _ = UserAcknowledgement.objects.filter(id__in=doomed).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} acknowledgement rows."))

    @staticmethod
    def _announcements_to_keep(cutoff):
        return set(Announcement.objects.filter(publish_end__gte=cutoff).values_list("id", flat=True))

    @staticmethod
    def _features_to_keep(cutoff):
        return set(
            Feature.objects.filter(is_active=True).filter(released_at__gte=cutoff.date()).values_list("id", flat=True)
        )
