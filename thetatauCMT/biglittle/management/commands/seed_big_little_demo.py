from django.core.management.base import BaseCommand, CommandError

from core.seed_guard import ensure_seeding_allowed
from thetatauCMT.biglittle import services
from thetatauCMT.biglittle.models import BigLittle
from thetatauCMT.chapters.models import Chapter


class Command(BaseCommand):
    help = (
        "Build a few generations of demo Big/Little pairings from a chapter's initiated members, "
        "in roll order, for local QA of the family tree. Safe to re-run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--chapter", required=True, help="Chapter slug, for example alpha.")
        parser.add_argument("--reset", action="store_true", help="Delete the chapter's pairings first.")
        parser.add_argument("--force", action="store_true", help="Run even when DEBUG is off.")

    def handle(self, *args, **options):
        ensure_seeding_allowed(force=options["force"])
        chapter = Chapter.objects.filter(slug=options["chapter"]).first()
        if chapter is None:
            raise CommandError(f"No chapter with the slug {options['chapter']!r}.")
        if options["reset"]:
            BigLittle.objects.filter(chapter=chapter).delete()
        members = list(services.eligible_members(chapter).order_by("badge_number", "pk"))
        if len(members) < 2:
            raise CommandError(f"{chapter} needs at least two initiated members.")
        founders = max(1, min(3, len(members) // 4))
        recorded = 0
        for index in range(founders, len(members)):
            little = members[index]
            if services.current_big_link(little) is not None:
                continue
            # Older members take one or two Littles each, so the tree has twins and several families.
            big = members[(index - founders) * 2 // 3]
            services.set_big(little, big, source=BigLittle.Source.ADMIN, chapter=chapter)
            recorded += 1
        changed = self._change_one_big(members, founders, chapter)
        self.stdout.write(f"Recorded {recorded} pairing(s) and changed {changed} Big(s) for {chapter}.")

    def _change_one_big(self, members, founders, chapter):
        """Give the newest member a different founder as Big, once, so admin shows an ended row."""
        last = members[-1]
        original = members[(len(members) - 1 - founders) * 2 // 3]
        link = services.current_big_link(last)
        if len(members) <= founders + 1 or link is None or link.big != original:
            return 0
        replacement = members[0] if original != members[0] else members[1]
        if replacement == last:
            return 0
        services.set_big(last, replacement, source=BigLittle.Source.ADMIN, chapter=chapter)
        return 1
