from dj_anonymizer.register_models import AnonymBase, register_clean, register_skip

from thetatauCMT.attendance.models import AttendanceRecord, AttendanceStatusTransition, MatchQueueItem

# Attendance records reference members only through foreign keys (anonymized via
# the User model), so they carry no direct PII and are useful test data.
register_skip([AttendanceRecord, AttendanceStatusTransition])

# MatchQueueItem stores raw, as-uploaded identity fields (emails, names, the full
# original CSV row) for national-event attendance matching — real personal data.
# It is a transient processing queue, so drop every row.
register_clean(
    [
        (MatchQueueItem, AnonymBase),
    ]
)
