from dj_anonymizer.register_models import AnonymBase, register_clean, register_skip
from herald.models import Notification, SentNotification, UserNotification

register_skip([UserNotification, Notification])

# This stores a complete message sent to users
register_clean(
    [
        (SentNotification, AnonymBase),
    ]
)
