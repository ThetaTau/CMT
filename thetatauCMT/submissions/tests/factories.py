import datetime

import factory

from thetatauCMT.chapters.tests.factories import ChapterFactory
from thetatauCMT.scores.models import ScoreType
from thetatauCMT.users.tests.factories import UserFactory

from ..models import Submission


class SubmissionFactory(factory.django.DjangoModelFactory):
    created = factory.Faker(
        "date_time_between",
        start_date="-1y",
        end_date="+1y",
        tzinfo=datetime.timezone.utc,
    )
    modified = factory.Faker(
        "date_time_between",
        start_date="-1y",
        end_date="+1y",
        tzinfo=datetime.timezone.utc,
    )
    user = factory.SubFactory(UserFactory)
    date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    file = factory.django.FileField(filename="test.pdf")
    name = factory.Faker("sentence", nb_words=3)
    type = factory.Iterator(ScoreType.objects.filter(type="Sub"))
    chapter = factory.SubFactory(ChapterFactory)

    class Meta:
        model = Submission
