import factory
from ..models import Region


class RegionFactory(factory.django.DjangoModelFactory):
    name = factory.Faker("name")
    email = factory.Faker("email")
    website = factory.Faker("uri")
    facebook = factory.Faker("uri")

    class Meta:
        model = Region
        django_get_or_create = ("name",)
