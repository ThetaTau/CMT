import factory
from django.utils import timezone

from thetatauCMT.attendance.models import AttendanceRecord
from thetatauCMT.events.tests.factories import EventFactory
from thetatauCMT.users.tests.factories import UserFactory


class AttendanceRecordFactory(factory.django.DjangoModelFactory):
    event = factory.SubFactory(EventFactory)
    user = factory.SubFactory(UserFactory)
    status = AttendanceRecord.STATUS.ATTENDED
    was_active = True
    chapter = factory.LazyAttribute(lambda o: o.user.chapter)
    recorded_at = factory.LazyFunction(timezone.now)

    class Meta:
        model = AttendanceRecord
