import factory
from ..models import Transaction
from chapters.tests.factories import ChapterFactory


class TransactionFactory(factory.django.DjangoModelFactory):
    created = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    modified = factory.Faker("date_time_between", start_date="-1y", end_date="+1y")
    type = factory.Faker(
        "random_element", elements=[item[0] for item in Transaction.TYPES]
    )
    due_date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
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
