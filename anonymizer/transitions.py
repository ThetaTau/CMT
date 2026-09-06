from dj_anonymizer.register_models import AnonymBase, register_clean, register_skip

from thetatauCMT.transitions.models import (
    HandoffNotice,
    PositionOverride,
    ReportAcknowledgement,
    ReportAnswer,
    ReportAttachment,
    ReportObligation,
    ReportTemplate,
    TemplatePrompt,
    TransitionReport,
)

# PositionOverride/ReportTemplate/TemplatePrompt are admin-managed config and
# prompt-set content (TRWI-1/2), seeded via management commands -- no
# personal data. ReportObligation (TRWI-3) references a person only through
# the officer/role_change foreign keys (anonymized via the User model) and
# holds no raw identity fields of its own (dates, position keys, status).
# TransitionReport (TRWI-5) is likewise just metadata (chapter/position/
# author FK/status/dates) -- the actual authored content lives on
# ReportAnswer, not here. ReportAcknowledgement and HandoffNotice (TRWI-7)
# are pure bookkeeping too -- a read-receipt FK+timestamp and a notification
# dedupe FK+timestamp, respectively -- same category as guides.
# UserAcknowledgement, which this app's own Codebase Review Notes already
# treated as skip-safe.
register_skip(
    [
        PositionOverride,
        ReportTemplate,
        TemplatePrompt,
        ReportObligation,
        TransitionReport,
        ReportAcknowledgement,
        HandoffNotice,
    ]
)

# ReportAnswer.value and ReportAttachment.file are free-text/uploaded-document
# content officers write about their term -- the plan's own "candor risk" note
# says officers may write critically about NAMED INDIVIDUALS, so this is raw
# as-uploaded identity content (same category as attendance.MatchQueueItem),
# not just an FK reference. Drop every row.
register_clean(
    [
        (ReportAnswer, AnonymBase),
        (ReportAttachment, AnonymBase),
    ]
)
