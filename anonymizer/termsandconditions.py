from dj_anonymizer.register_models import register_skip, AnonymBase, register_anonym
from dj_anonymizer import fields
from faker import Factory

from termsandconditions.models import UserTermsAndConditions, TermsAndConditions

fake = Factory.create()

register_skip([TermsAndConditions])


class UserTermsAndConditionsAnonym(AnonymBase):
    ip_address = fields.function(fake.ipv4_public)

    class Meta:
        exclude_fields = ["date_accepted"]


register_anonym(
    [
        (UserTermsAndConditions, UserTermsAndConditionsAnonym),
    ]
)
