import random
import factory
from ..models import Ballot, BallotComplete
from users.tests.factories import UserFactory


class BallotFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    sender = factory.Faker("sentence", nb_words=3)
    name = factory.Faker("sentence", nb_words=3)
    type = factory.Faker(
        "random_element", elements=[item.value[0] for item in Ballot.TYPES]
    )
    # attachment = models.FileField
    description = factory.Faker("paragraph", nb_sentences=5)
    due_date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    voters = factory.Faker(
        "random_element", elements=[item.value[0] for item in Ballot.VOTERS]
    )

    @factory.post_generation
    def completed(self, create, extracted, **kwargs):
        return BallotCompleteFactory.create_batch(random.randint(0, 30), ballot=self)

    class Meta:
        model = Ballot
        django_get_or_create = ("name",)


class BallotCompleteFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    ballot = factory.SubFactory(BallotFactory)
    user = factory.SubFactory(UserFactory)
    motion = factory.Faker(
        "random_element", elements=[item.value[0] for item in BallotComplete.MOTION]
    )
    role = factory.Faker(
        "random_element", elements=[item[0] for item in BallotComplete.ROLES]
    )

    class Meta:
        model = BallotComplete
