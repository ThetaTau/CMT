from dj_anonymizer.register_models import AnonymBase, register_clean

from thetatauCMT.email_tracking.models import EmailTrackingEvent, TrackedEmail

# TrackedEmail / EmailTrackingEvent store recipient email addresses (and Mailjet's
# raw event payloads, which echo the recipient) — direct PII. In a de-identified
# staging database we drop every row, mirroring how herald's SentNotification is
# handled (see anonymizer/herald.py).
register_clean(
    [
        (TrackedEmail, AnonymBase),
        (EmailTrackingEvent, AnonymBase),
    ]
)
