from datetime import date
import factory
from scores.models import ScoreType
from chapters.tests.factories import ChapterFactory
from ..models import Event


class EventFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    name = factory.Faker("sentence", nb_words=3)
    date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    type = factory.Iterator(ScoreType.objects.filter(type="Evt"))
    chapter = factory.SubFactory(ChapterFactory)
    description = factory.Faker("paragraph", nb_sentences=2)
    members = factory.Faker("random_int", max=200)
    alumni = factory.Faker("random_int", max=200)
    pledges = factory.Faker("random_int", max=50)
    guests = factory.Faker("random_int", max=200)
    duration = factory.Faker("random_int", max=200)
    stem = factory.Faker("boolean")
    host = factory.Faker("boolean")
    miles = factory.Faker("random_int", max=5000)

    class Meta:
        model = Event

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        calculate_score = kwargs.pop("calculate_score", False)
        instance = model_class(**kwargs)
        instance.save(calculate_score=calculate_score)
        return instance
