from dj_anonymizer.register_models import register_skip
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from oauth2_provider.models import AccessToken, Application, Grant, IDToken, RefreshToken

register_skip(
    [
        StaticToken,
        StaticDevice,
        TOTPDevice,
        IDToken,
        RefreshToken,
        Grant,
        Application,
        AccessToken,
    ]
)
