# [event.save() for event in Event.objects.filter(type__slug="brotherhood")]
# python manage.py score_calculate_extras
import datetime
from django.core.management import BaseCommand
from chapters.models import Chapter
from scores.models import ScoreType, ScoreChapter


class Command(BaseCommand):
    # Show this when the user types help
    help = "Calculate scores for extra types"

    # A command must define handle()
    def handle(self, *args, **options):
        """
        python manage.py score_calculate_extras

        Current size is # active actives on March 15th and November 15th
        This is when dues are calculated and due
        From semester start to end count pledge forms, init forms, grad forms
        - % Pledged vs % Initiated
        - Membership

        - Adopted New Member Education Program
        - Annual Report Review

        If an object is not found, get_or_create() will instantiate and save a new object
        """
        chapters = Chapter.objects.all()
        for chapter in chapters:
            print(chapter)
            for year in range(2016, 2022):
                for semester in ["sp", "fa"]:
                    print("    ", year, ":", semester)
                    date = datetime.date(year, 11, 15)
                    if semester == "sp":
                        date = datetime.date(year, 3, 15)

                    # % Pledged vs % Initiated
                    # This does NOT handle chapters that often pledge in fall
                    #   and then init in January once freshmen pledge have GPA
                    #       Mabybe get list of pledges and check each for init?
                    # initiated = chapter.initiations_semester(date).count()
                    pledges = chapter.pledges_semester(date)
                    # only those members that have an initiation form were initiated
                    initiated = pledges.exclude(initiation=None).count()
                    pledged = max([pledges.count(), 1])
                    # 10 * (# Initiated / # Pledged)
                    pledge_vs_init_score = min(
                        [10, round(10 * (initiated / pledged), 2)]
                    )
                    score_type = ScoreType.objects.get(slug="pledge-ratio")
                    ScoreChapter.objects.get_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(score=pledge_vs_init_score,),
                    )

                    # Membership
                    # 50 * (Current_Size *  # Initiated) / (# Graduating_Members * 2)
                    current_size = chapter.get_actives_for_date(date).count()
                    graduated = max([chapter.graduates(date).count(), 1])
                    membership_score = min(
                        [25, round(((current_size * initiated) / (graduated * 2)), 2),]
                    )
                    score_type = ScoreType.objects.get(slug="membership")
                    ScoreChapter.objects.get_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(score=membership_score,),
                    )
                    print(
                        f"        Init: {initiated}, Pledged: {pledged}, Current: {current_size}, grad: {graduated}"
                    )
                    # Annual Report Review
                    # if chapter had any events reported they get annual report calc
                    # 5 per inspection; 10/semester
                    events = chapter.events_semester().count()
                    report_review_score = 0
                    if events > 1:
                        report_review_score = 10
                    score_type = ScoreType.objects.get(slug="report")
                    ScoreChapter.objects.get_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(score=report_review_score,),
                    )

                    # Adopted New Member Education Program
                    # 20*UNMODIFIED+10*MODIFIED
                    program_score = 10
                    score_type = ScoreType.objects.get(slug="pledge-program")
                    ScoreChapter.objects.get_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(score=program_score,),
                    )
                # Only needs to be done once per year
                for score_type in ScoreType.objects.filter(type__in=["Evt", "Sub"]):
                    score_type.update_chapter_score(chapter, date)
