from dj_anonymizer.register_models import register_skip

from thetatauCMT.biglittle.models import BigLittle

# A pairing points at members only through foreign keys (anonymized via the User
# model) plus a source choice and timestamps, so the rows are safe staging data.
register_skip([BigLittle])
