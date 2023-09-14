import datetime
import factory
from ..models import (
    UserAlter,
    UserSemesterServiceHours,
    UserSemesterGPA,
    UserStatusChange,
    UserRoleChange,
    UserOrgParticipate,
    Role,
)
from chapters.tests.factories import ChapterFactory, ChapterCurriculaFactory


class UserFactory(factory.django.DjangoModelFactory):
    email = factory.Sequence(lambda n: f"user-{n}@example.com")
    password = factory.PostGenerationMethodCall("set_password", "password")
    username = factory.LazyAttribute(lambda o: o.email)
    user_id = factory.LazyAttribute(lambda o: f"{o.chapter.greek}{o.badge_number}")
    name = factory.Faker("name")
    title = factory.Faker("random_element", elements=["mr", "miss", "ms", "mrs"])
    first_name = factory.Faker("first_name")
    middle_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    suffix = factory.Faker("suffix")
    nickname = factory.Faker("name")
    email_school = factory.Faker("email")
    birth_date = factory.Faker("date_of_birth", minimum_age=18, maximum_age=70)
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    badge_number = factory.Sequence(lambda n: n + 1)
    major = factory.SubFactory(ChapterCurriculaFactory)
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
        django_get_or_create = ("username", "user_id")

    @factory.post_generation
    def make_officer(self, create, extracted, **kwargs):
        if extracted:
            current = kwargs.get("current", True)
            UserRoleChangeFactory.create(
                user=self,
                current=current,
                officer=extracted,
            )

    @factory.post_generation
    def status(self, create, extracted, **kwargs):
        if extracted:
            UserStatusChangeFactory.create(user=self, current=True, status=extracted)


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
        "random_element",
        elements=[item.value[0] for item in UserSemesterGPA.TERMS],
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

    @factory.post_generation
    def current(self, create, extracted, **kwargs):
        if extracted:
            self.start = factory.Faker("date_between", start_date="-4y").generate()
            self.end = factory.Faker(
                "date_between", start_date="+1d", end_date="+4y"
            ).generate()


class UserRoleChangeFactory(factory.django.DjangoModelFactory):
    start = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    end = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    user = factory.SubFactory(UserFactory)
    role = factory.Faker(
        "random_element", elements=[item[0] for item in Role.roles_in_group_choices()]
    )

    class Meta:
        model = UserRoleChange

    @factory.post_generation
    def current(self, create, extracted, **kwargs):
        if extracted:
            self.start = factory.Faker("date_between", start_date="-4y").generate()
            self.end = factory.Faker(
                "date_between", start_date="+1d", end_date="+4y"
            ).generate()
        else:
            self.end = factory.Faker(
                "date_between", start_date="-239d", end_date="-1d"
            ).generate()

    @factory.post_generation
    def officer(self, create, extracted, **kwargs):
        if extracted == "chapter":
            elements = Role.officers("chapter")
        elif extracted == "national":
            elements = Role.officers("national")
        elif extracted == "advisor":
            elements = Role.roles_in_group(groups=["advisor"])
        else:
            elements = [extracted]
        self.role = factory.Faker("random_element", elements=elements).generate()


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
