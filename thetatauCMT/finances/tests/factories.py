import datetime
from decimal import Decimal

import factory
from djmoney.money import Money

from thetatauCMT.chapters.tests.factories import ChapterFactory

from ..models import Invoice


class InvoiceFactory(factory.django.DjangoModelFactory):
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
    due_date = factory.Faker("date_between", start_date="-4y", end_date="+4y")
    central_id = factory.Faker("bothify", text="INV-####")
    description = factory.Faker("paragraph", nb_sentences=5)
    total = factory.LazyFunction(lambda: Money(Decimal("100.00"), "USD"))
    chapter = factory.SubFactory(ChapterFactory)

    class Meta:
        model = Invoice
