import random
import factory
from ..models import Transaction
from chapters.tests.factories import ChapterFactory


class TransactionFactory(factory.django.DjangoModelFactory):
    type = factory.Faker(
        "random_element", elements=[item.value[0] for item in Transaction.TYPES]
    )
    due_date = factory.Faker("date")
    central_id = factory.Faker("random_int")
    description = factory.Faker("paragraph", nb_sentences=5)
    paid = factory.Faker("boolean")
    quantity = factory.Faker("random_int")
    # Maybe try own faker provider? https://github.com/django-money/django-money/issues/297
    unit_cost = None
    total = None
    chapter = factory.SubFactory(ChapterFactory)
    estimate = factory.Faker("boolean")

    class Meta:
        model = Transaction
