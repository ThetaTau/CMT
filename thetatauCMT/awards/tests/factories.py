import datetime

import factory
from django.utils import timezone

from thetatauCMT.users.tests.factories import UserFactory

from ..flows import AwardNominationFlow
from ..models import AwardCycle, AwardGrant, AwardNominationProcess, AwardType, EligibilityRule


class AwardTypeFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Award {n}")
    description = factory.Faker("sentence")
    level = AwardType.Level.MEMBER
    grant_method = AwardType.GrantMethod.DIRECT
    recurrence = AwardType.Recurrence.ONE_TIME

    class Meta:
        model = AwardType


class AwardCycleFactory(factory.django.DjangoModelFactory):
    name = factory.Sequence(lambda n: f"Cycle {n}")
    period_type = AwardCycle.PeriodType.YEAR
    # Dated and open-ended, so the default factory cycle is a *current* period.
    start_date = factory.LazyFunction(lambda: datetime.date(timezone.now().year, 1, 1))

    class Meta:
        model = AwardCycle


class AwardGrantFactory(factory.django.DjangoModelFactory):
    award_type = factory.SubFactory(AwardTypeFactory)
    cycle = factory.SubFactory(AwardCycleFactory)
    recipient_member = factory.SubFactory(UserFactory)
    granted_by = factory.SubFactory(UserFactory)

    class Meta:
        model = AwardGrant


class EligibilityRuleFactory(factory.django.DjangoModelFactory):
    award_type = factory.SubFactory(AwardTypeFactory)
    rule_type = EligibilityRule.RuleType.MEMBER_STATUS

    class Meta:
        model = EligibilityRule


class AwardNominationProcessFactory(factory.django.DjangoModelFactory):
    flow_class = AwardNominationFlow
    award_type = factory.SubFactory(AwardTypeFactory)
    cycle = factory.SubFactory(AwardCycleFactory)
    recipient_member = factory.SubFactory(UserFactory)
    nominator = factory.SubFactory(UserFactory)

    class Meta:
        model = AwardNominationProcess
