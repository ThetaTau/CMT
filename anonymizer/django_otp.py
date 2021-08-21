from dj_anonymizer.register_models import register_skip

from django_otp.plugins.otp_static.models import StaticToken, StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

register_skip([StaticToken, StaticDevice, TOTPDevice])
