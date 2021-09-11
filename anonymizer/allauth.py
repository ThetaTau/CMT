from dj_anonymizer.register_models import (
    register_skip,
    AnonymBase,
    register_anonym,
    register_clean,
)
from dj_anonymizer import anonym_field
from faker import Factory

from allauth.socialaccount.models import SocialToken, SocialAccount, SocialApp
from allauth.account.models import EmailConfirmation, EmailAddress

register_skip([EmailConfirmation, SocialToken, SocialApp])
register_clean([SocialAccount])

fake = Factory.create()


class EmailAddressAnonym(AnonymBase):
    email = anonym_field.string("{seq}@thetatau.org")
    verified = anonym_field.function(lambda: True)

    class Meta:
        exclude_fields = ["primary"]


register_anonym(
    [
        (EmailAddress, EmailAddressAnonym),
    ]
)
