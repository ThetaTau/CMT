import random
import factory
from chapters.models import Chapter, ChapterCurricula, GREEK_ABR
from regions.tests.factories import RegionFactory


GREEK_ABR_NAME = {v: k for k, v in GREEK_ABR.items()}


class ChapterFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("random_element", elements=GREEK_ABR.values())
    region = factory.SubFactory(RegionFactory)
    email = factory.Faker("email")
    website = factory.Faker("uri")
    facebook = factory.Faker("uri")
    address = factory.Faker("address")
    balance = factory.Faker("pydecimal", left_digits=5, right_digits=2)
    balance_date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    tax = factory.Faker("random_int")
    greek = factory.LazyAttribute(lambda o: GREEK_ABR_NAME[o.name.lower()])
    active = True
    colony = False
    school = factory.LazyAttribute(lambda o: f"{o.name} SCHOOL")
    latitude = factory.Faker("latitude")
    longitude = factory.Faker("longitude")
    school_type = factory.Faker(
        "random_element", elements=[item[0] for item in Chapter.TYPES]
    )
    council = factory.Faker("text", max_nb_chars=55)
    recognition = factory.Faker(
        "random_element", elements=[item.value[0] for item in Chapter.RECOGNITION]
    )

    @factory.post_generation
    def curricula(self, create, extracted, **kwargs):
        return ChapterCurriculaFactory.create_batch(random.randint(0, 15), chapter=self)

    class Meta:
        model = Chapter
        django_get_or_create = ("name",)


class ChapterCurriculaFactory(factory.django.DjangoModelFactory):
    chapter = factory.SubFactory(ChapterFactory)
    major = factory.Faker("sentence", nb_words=3)

    class Meta:
        model = ChapterCurricula
