import factory

from ..models import Audience, Feature, FeatureArea, RoleGuide, RoleGuideStep


class FeatureAreaFactory(factory.django.DjangoModelFactory):
    key = factory.Sequence(lambda n: f"area-{n}")
    name = factory.Sequence(lambda n: f"Area {n}")
    description = factory.Faker("sentence")
    audience = Audience.MEMBER

    class Meta:
        model = FeatureArea


class FeatureFactory(factory.django.DjangoModelFactory):
    area = factory.SubFactory(FeatureAreaFactory)
    key = factory.Sequence(lambda n: f"feature-{n}")
    name = factory.Sequence(lambda n: f"Feature {n}")
    short_description = factory.Faker("sentence")

    class Meta:
        model = Feature


class RoleGuideFactory(factory.django.DjangoModelFactory):
    # ``role`` must be a real ``core.models.ALL_ROLES`` value -- the model
    # validates it, and it doubles as the join to ``tasks.Task.owner``.
    role = "treasurer"
    title = factory.LazyAttribute(lambda guide: guide.role.title())
    summary = factory.Faker("sentence")

    class Meta:
        model = RoleGuide
        django_get_or_create = ("role",)


class RoleGuideStepFactory(factory.django.DjangoModelFactory):
    guide = factory.SubFactory(RoleGuideFactory)
    title = factory.Sequence(lambda n: f"Guide step {n}")
    body = factory.Faker("sentence")

    class Meta:
        model = RoleGuideStep
