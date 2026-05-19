from address.models import Address, Country, Locality, State
from dj_anonymizer import fields
from dj_anonymizer.register_models import AnonymBase, register_anonym, register_skip
from faker import Factory

fake = Factory.create()
register_skip([Locality, State, Country])


class AddressAnonym(AnonymBase):
    street_number = fields.function(fake.building_number)
    route = fields.function(fake.street_name)
    raw = fields.function(fake.address)
    formatted = fields.function(fake.address)
    latitude = fields.function(fake.latitude)
    longitude = fields.function(fake.longitude)

    class Meta:
        pass


register_anonym(
    [
        (Address, AddressAnonym),
    ]
)
