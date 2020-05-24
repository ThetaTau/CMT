import factory
from ..models import ScoreType, ScoreChapter
from chapters.tests.factories import ChapterFactory


# class ScoreTypeFactory(factory.django.DjangoModelFactory):
#     name = factory.Faker("sentence", nb_words=3)
#     description = factory.Faker("sentence", nb_words=8)
#     section = factory.Faker(
#         "random_element", elements=[item.value[0] for item in ScoreType.SECTION]
#     )
#     points = factory.Faker("random_int")
#     term_points = factory.Faker("random_int")
#     formula = ""
#     slug = factory.LazyAttribute(lambda o: slugify(o.name))
#     type = factory.Faker(
#         "random_element", elements=[item.value[0] for item in ScoreType.TYPES]
#     )
#     base_points = factory.Faker("pyfloat")
#     attendance_multiplier = factory.Faker("pyfloat")
#     member_add = factory.Faker("pyfloat")
#     stem_add = factory.Faker("pyfloat")
#     alumni_add = factory.Faker("pyfloat")
#     guest_add = factory.Faker("pyfloat")
#     special = ""
#
#     @factory.post_generation
#     def chapters(self, create, extracted, **kwargs):
#         return ScoreChapterFactory.create_batch(random.randint(0, 30), type=self)
#
#     class Meta:
#         model = ScoreType
#         django_get_or_create = ("name",)


class ScoreChapterFactory(factory.django.DjangoModelFactory):
    chapter = factory.SubFactory(ChapterFactory)
    type = factory.Iterator(ScoreType.objects.all())
    score = factory.LazyAttribute(
        lambda o: factory.Faker(
            "pyfloat", min_value=0, max_value=o.type.term_points
        ).generate({})
    )
    year = factory.Faker(
        "random_element", elements=[item[0] for item in ScoreChapter.YEARS]
    )
    term = factory.Faker(
        "random_element", elements=[item.value[0] for item in ScoreChapter.TERMS]
    )

    class Meta:
        model = ScoreChapter
