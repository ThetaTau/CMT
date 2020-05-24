import factory
from scores.models import ScoreType
from chapters.tests.factories import ChapterFactory
from users.tests.factories import UserFactory
from ..models import Submission


class SubmissionFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    user = factory.SubFactory(UserFactory)
    date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    file = factory.django.FileField(filename="test.pdf")
    name = factory.Faker("sentence", nb_words=3)
    type = factory.Iterator(ScoreType.objects.filter(type="Sub"))
    chapter = factory.SubFactory(ChapterFactory)

    class Meta:
        model = Submission
