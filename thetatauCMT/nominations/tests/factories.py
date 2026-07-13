import factory

from thetatauCMT.users.tests.factories import UserFactory

from ..flows import NominationFlow
from ..models import Nomination


class NominationFactory(factory.django.DjangoModelFactory):
    flow_class = NominationFlow
    nominee = factory.SubFactory(UserFactory)
    nominator = factory.SubFactory(UserFactory)
    level = "national"
    reason = factory.Faker("sentence")
    discussed_with_nominee = True

    class Meta:
        model = Nomination
