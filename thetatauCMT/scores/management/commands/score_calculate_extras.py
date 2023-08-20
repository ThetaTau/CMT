# [event.save() for event in Event.objects.filter(type__slug="brotherhood")]
# python manage.py score_calculate_extras
import datetime
from django.core.management import BaseCommand
from django.db.models import Sum
from core.models import BIENNIUM_YEARS
from chapters.models import Chapter
from scores.models import ScoreType, ScoreChapter
from users.models import (
    UserSemesterGPA,
    UserSemesterServiceHours,
    UserOrgParticipate,
)


class Command(BaseCommand):
    # Show this when the user types help
    help = "Calculate scores for extra types"

    def add_arguments(self, parser):
        parser.add_argument("year_start", nargs=1, type=str)
        parser.add_argument("year_end", nargs=1, type=str)

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

        If an object is not found, update_or_create() will instantiate and save a new object
        """
        year_start = int(options.get("year_start", [BIENNIUM_YEARS[0]])[0])
        year_end = int(options.get("year_end", [BIENNIUM_YEARS[-1]])[0])
        chapters = Chapter.objects.all()
        for chapter in chapters:
            print(chapter)
            for year in range(year_start, year_end + 1):
                for semester in ["sp", "fa"]:
                    # print("    ", year, ":", semester)
                    date = datetime.date(year, 11, 15)
                    if semester == "sp":
                        date = datetime.date(year, 3, 15)

                    # % Pledged vs % Initiated
                    pledges = chapter.pledges_semester(date)
                    # only those members that have an initiation form were initiated
                    initiated = pledges.exclude(initiation=None).count()
                    pledged = max([pledges.count(), 1])
                    # 10 * (# Initiated / # Pledged)
                    pledge_vs_init_score = min(
                        [10, round(10 * (initiated / pledged), 2)]
                    )
                    score_type = ScoreType.objects.get(slug="pledge-ratio")
                    ScoreChapter.objects.update_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(
                            score=pledge_vs_init_score,
                        ),
                    )

                    # Membership
                    # 50 * (Current_Size *  # Initiated) / (# Graduating_Members * 2)
                    current_size = chapter.get_actives_for_date(date).count()
                    current_size = current_size if current_size else 1
                    graduated = max([chapter.graduates(date).count(), 1])
                    membership_score = min(
                        [
                            25,
                            round(((current_size * initiated) / (graduated * 2)), 2),
                        ]
                    )
                    score_type = ScoreType.objects.get(slug="membership")
                    ScoreChapter.objects.update_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(
                            score=membership_score,
                        ),
                    )
                    # print(
                    #     f"        Init: {initiated}, Pledged: {pledged}, Current: {current_size}, grad: {graduated}"
                    # )

                    # Service Hours
                    # 50 * [total hours / (  # brothers * 16)]
                    total_hours = UserSemesterServiceHours.objects.filter(
                        user__chapter=chapter, year=year, term=semester
                    ).aggregate(Sum("service_hours"))["service_hours__sum"]
                    total_hours = total_hours if total_hours else 0
                    service_score = 50 * (total_hours / (current_size * 16))
                    service_score = round(min(50, service_score), 2)
                    score_type = ScoreType.objects.get(slug="service-hours")
                    # print("        ", score_type, service_score)
                    (obj, created) = ScoreChapter.objects.update_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(
                            score=service_score,
                        ),
                    )
                    # print("            ", obj.score)
                    # GPA
                    # (Chapter GPA Average / 3.5) x 30 /semester
                    total_gpa = UserSemesterGPA.objects.filter(
                        user__chapter=chapter, year=year, term=semester
                    ).aggregate(Sum("gpa"))["gpa__sum"]
                    total_gpa = total_gpa if total_gpa else 0
                    gpa_score = 30 * ((total_gpa / current_size) / 3.5)
                    gpa_score = round(min(20, gpa_score), 2)
                    score_type = ScoreType.objects.get(slug="gpa")
                    # print("        ", score_type, gpa_score)
                    (obj, created) = ScoreChapter.objects.update_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(
                            score=gpa_score,
                        ),
                    )
                    # print("            ", obj.score)
                    # ORGS
                    # 10 * (% Participating) + (2 per officer)
                    orgs = UserOrgParticipate.objects.filter(
                        user__chapter=chapter, start__lte=date, end__gte=date
                    )
                    total_orgs = orgs.count()
                    officer = orgs.filter(officer=True).count()
                    org_score = (10 * (total_orgs / current_size)) + (2 * officer)
                    org_score = round(min(20, org_score), 2)
                    score_type = ScoreType.objects.get(slug="societies")
                    # print("        ", score_type, org_score)
                    (obj, created) = ScoreChapter.objects.update_or_create(
                        chapter=chapter,
                        type=score_type,
                        year=year,
                        term=semester,
                        defaults=dict(
                            score=org_score,
                        ),
                    )
                    # print("            ", obj.score)

                # Only needs to be done once per year
                for score_type in ScoreType.objects.filter(type__in=["Evt", "Sub"]):
                    score_type.update_chapter_score(chapter, date)
