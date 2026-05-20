from allauth.account.models import EmailAddress, EmailConfirmation
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from dj_anonymizer import fields
from dj_anonymizer.register_models import AnonymBase, register_anonym, register_clean, register_skip
from faker import Factory

register_skip([EmailConfirmation, SocialToken, SocialApp])
register_clean(
    [
        (SocialAccount, AnonymBase),
    ]
)

fake = Factory.create()


class EmailAddressAnonym(AnonymBase):
    email = fields.string("{seq}@thetatau.org")
    verified = fields.function(lambda: True)

    class Meta:
        exclude_fields = ["primary"]


register_anonym(
    [
        (EmailAddress, EmailAddressAnonym),
    ]
)
