from datetime import timedelta

import factory
from django.utils import timezone

from thetatauCMT.announcements.models import Announcement


class AnnouncementFactory(factory.django.DjangoModelFactory):
    """A currently published announcement with every TWI-6 field left at default.

    The defaults matter: a row built by this factory must behave exactly like a
    row that predates TWI-6, which is what the backwards-compatibility tests
    assert.
    """

    class Meta:
        model = Announcement

    title = factory.Sequence(lambda n: f"Announcement {n}")
    content = "<p>Something happened.</p>"
    priority = 5
    publish_start = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))
    publish_end = factory.LazyFunction(lambda: timezone.now() + timedelta(days=30))
