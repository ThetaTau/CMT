from users.tests.factories import UserFactory, UserSemesterGPAFactory
from chapters.tests.factories import ChapterFactory
from chapters.models import Chapter
from users.models import User, UserStatusChange, UserSemesterGPA


def run(*args):
    if "clear" in args:
        value = input("Are you sure?\n")
        if value == "Yes":
            User.objects.all().delete()
            UserStatusChange.objects.all().delete()
    chapter = ChapterFactory.create()
    print(chapter)

    UserSemesterGPAFactory.create_batch(
        40, user__chapter=chapter, user__status="active"
    )
    UserSemesterGPAFactory.create_batch(
        40, user__chapter=chapter, user__status="alumni"
    )
    UserSemesterGPAFactory.create_batch(
        40, user__chapter=chapter, user__status="alumnipend"
    )
    UserSemesterGPAFactory.create_batch(40, user__chapter=chapter, user__status="pnm")
    UserSemesterGPAFactory.create_batch(
        40, user__chapter=chapter, user__status="activepend"
    )
    UserSemesterGPAFactory.create_batch(
        40, user__chapter=chapter, user__status="depledge"
    )
    UserSemesterGPAFactory.create_batch(40, user__chapter=chapter, user__status="away")

    """
    UserFactory.create_batch(10, chapter=chapter, status="active", graduation_year=2020)
    UserFactory.create_batch(15, chapter=chapter, status="active", graduation_year=2021)
    UserFactory.create_batch(17, chapter=chapter, status="active", graduation_year=2022)
    UserFactory.create_batch(5, chapter=chapter, status="active", graduation_year=2023)

    UserFactory.create_batch(10, chapter=chapter, status="alumni", graduation_year=2019)
    UserFactory.create_batch(6, chapter=chapter, status="alumni", graduation_year=2018)
    UserFactory.create_batch(7, chapter=chapter, status="alumni", graduation_year=2017)
    UserFactory.create_batch(8, chapter=chapter, status="alumni", graduation_year=2016)
    UserFactory.create_batch(12, chapter=chapter, status="alumni", graduation_year=2015)

    UserFactory.create_batch(
        5, chapter=chapter, status="alumnipend", graduation_year=2019
    )
    UserFactory.create_batch(
        3, chapter=chapter, status="alumnipend", graduation_year=2018
    )
    UserFactory.create_batch(
        7, chapter=chapter, status="alumnipend", graduation_year=2017
    )
    UserFactory.create_batch(
        4, chapter=chapter, status="alumnipend", graduation_year=2016
    )
    UserFactory.create_batch(
        6, chapter=chapter, status="alumnipend", graduation_year=2015
    )

    UserFactory.create_batch(2, chapter=chapter, status="pnm", graduation_year=2021)
    UserFactory.create_batch(6, chapter=chapter, status="pnm", graduation_year=2022)
    UserFactory.create_batch(5, chapter=chapter, status="pnm", graduation_year=2023)
    UserFactory.create_batch(2, chapter=chapter, status="depledge")
    """

