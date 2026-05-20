from dj_anonymizer import fields
from dj_anonymizer.register_models import AnonymBase, register_anonym, register_skip
from faker import Factory
from termsandconditions.models import TermsAndConditions, UserTermsAndConditions

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
