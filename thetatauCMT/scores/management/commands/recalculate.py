import datetime
from django.core.management import BaseCommand

from chapters.models import Chapter
from scores.models import ScoreType
from core.models import BIENNIUM_START


class Command(BaseCommand):
    # Show this when the user types help
    help = "Recalculate scores"

    def add_arguments(self, parser):
        parser.add_argument("score_type", nargs=1, type=str)
        parser.add_argument("-chapter", nargs=1, type=str)

    # A command must define handle()
    def handle(self, *args, **options):
        """
        python manage.py recalculate meetings -chapter zeta
        """
        print(options)
        chapter_only = options.get("chapter", None)
        score_type = options.get("score_type", [None])[0]
        print(f"Recalculating for score_type {score_type}")
        if score_type is None:
            print("You must supply score_type")
            return
        if chapter_only:
            chapter_only = chapter_only[0]
            chapters = Chapter.objects.filter(slug=chapter_only)
            print(f"Recalculating for chapter {chapters}")
        else:
            chapters = Chapter.objects.filter(active=True)
        score_type = ScoreType.objects.get(slug=score_type)
        for chapter in chapters:
            print(chapter)
            if score_type.type == "Evt":
                objects = chapter.events.filter(
                    date__gte=datetime.date(BIENNIUM_START, 8, 1), type=score_type
                )
            elif score_type.type == "Sub":
                objects = chapter.submissions.filter(
                    date__gte=datetime.date(BIENNIUM_START, 8, 1), type=score_type
                )
            print(f"    Found {objects.count()} to recalculate")
            for obj in objects:
                obj.save(calculate_score=True)
