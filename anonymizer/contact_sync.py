from dj_anonymizer.register_models import AnonymBase, register_clean

from thetatauCMT.contact_sync.models import UserContactSyncToken

# UserContactSyncToken holds encrypted OAuth access/refresh tokens (secrets) and
# the connected provider account email — real credentials that must never reach
# staging. Drop every row; officers reconnect their provider accounts as needed.
register_clean(
    [
        (UserContactSyncToken, AnonymBase),
    ]
)
