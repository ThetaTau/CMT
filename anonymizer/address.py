from dj_anonymizer.register_models import AnonymBase, register_anonym, register_skip
from dj_anonymizer import anonym_field
from faker import Factory

from address.models import Locality, State, Country, Address

fake = Factory.create()
register_skip([Locality, State, Country])


class AddressAnonym(AnonymBase):
    street_number = anonym_field.function(fake.building_number)
    route = anonym_field.function(fake.street_name)
    raw = anonym_field.function(fake.address)
    formatted = anonym_field.function(fake.address)
    latitude = anonym_field.function(fake.latitude)
    longitude = anonym_field.function(fake.longitude)

    class Meta:
        pass


register_anonym(
    [
        (Address, AddressAnonym),
    ]
)
