import datetime
import factory
from ..models import (
    UserAlter,
    UserSemesterServiceHours,
    UserSemesterGPA,
    UserStatusChange,
    UserRoleChange,
    UserOrgParticipate,
)
from chapters.tests.factories import ChapterFactory


class UserFactory(factory.django.DjangoModelFactory):
    email = factory.Sequence(lambda n: f"user-{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password")
    username = factory.LazyAttribute(lambda o: o.email)
    name = factory.Faker("name")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    badge_number = factory.Faker("random_int", min=1950, max=999999999)
    title = factory.Faker("prefix")
    major = factory.Faker("sentence", nb_words=3)
    employer = factory.Faker("sentence", nb_words=3)
    employer_position = factory.Faker("sentence", nb_words=3)
    graduation_year = factory.Faker(
        "random_int", min=1950, max=datetime.datetime.now().year + 10
    )
    phone_number = factory.Faker("msisdn")
    address = factory.Faker("address")
    chapter = factory.SubFactory(ChapterFactory)

    class Meta:
        model = "users.User"
        django_get_or_create = ("username",)


class UserAlterFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory(UserFactory)
    chapter = factory.SubFactory(ChapterFactory)
    role = factory.Faker(
        "random_element", elements=[item[0] for item in UserAlter.ROLES]
    )

    class Meta:
        model = UserAlter


class UserSemesterServiceHoursFactory(factory.django.DjangoModelFactory):
    year = factory.Faker(
        "random_element", elements=[item[0] for item in UserSemesterServiceHours.YEARS]
    )
    term = factory.Faker(
        "random_element",
        elements=[item.value[0] for item in UserSemesterServiceHours.TERMS],
    )
    user = factory.SubFactory(UserFactory)
    service_hours = factory.Faker("pyfloat", min_value=0, max_value=1000)

    class Meta:
        model = UserSemesterServiceHours


class UserSemesterGPAFactory(factory.django.DjangoModelFactory):
    year = factory.Faker(
        "random_element", elements=[item[0] for item in UserSemesterGPA.YEARS]
    )
    term = factory.Faker(
        "random_element", elements=[item.value[0] for item in UserSemesterGPA.TERMS],
    )
    user = factory.SubFactory(UserFactory)
    gpa = factory.Faker("pyfloat", min_value=0, max_value=20)

    class Meta:
        model = UserSemesterGPA


class UserStatusChangeFactory(factory.django.DjangoModelFactory):
    start = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    end = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    user = factory.SubFactory(UserFactory)
    status = factory.Faker(
        "random_element", elements=[item[0] for item in UserStatusChange.STATUS]
    )

    class Meta:
        model = UserStatusChange


class UserRoleChangeFactory(factory.django.DjangoModelFactory):
    start = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    end = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    user = factory.SubFactory(UserFactory)
    role = factory.Faker(
        "random_element", elements=[item[0] for item in UserRoleChange.ROLES]
    )

    class Meta:
        model = UserRoleChange


class UserOrgParticipateFactory(factory.django.DjangoModelFactory):
    start = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    end = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    user = factory.SubFactory(UserFactory)
    org_name = factory.Faker("sentence", nb_words=3)
    type = factory.Faker(
        "random_element", elements=[item[0] for item in UserOrgParticipate.TYPES]
    )
    officer = factory.Faker("boolean")

    class Meta:
        model = UserOrgParticipate
