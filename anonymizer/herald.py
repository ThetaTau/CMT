from dj_anonymizer.register_models import register_skip, register_clean

from herald.models import SentNotification, UserNotification, Notification

register_skip([UserNotification, Notification])

# This stores a complete message sent to users
register_clean([SentNotification])
