from dj_anonymizer.register_models import AnonymBase, register_clean, register_skip

from thetatauCMT.biglittle.models import BigLittle, PendingPairing

# A pairing points at members only through foreign keys (anonymized via the User
# model) plus a source choice and timestamps, so the rows are safe staging data.
register_skip([BigLittle])

# PendingPairing keeps the names exactly as typed in an uploaded spreadsheet, which is
# real personal data. It is a short-lived review queue, so drop every row.
register_clean(
    [
        (PendingPairing, AnonymBase),
    ]
)
