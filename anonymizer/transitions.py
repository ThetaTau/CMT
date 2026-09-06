from dj_anonymizer.register_models import AnonymBase, register_clean, register_skip

from thetatauCMT.transitions.models import (
    HandoffNotice,
    PositionOverride,
    ReportAcknowledgement,
    ReportAnswer,
    ReportAttachment,
    ReportObligation,
    ReportTag,
    ReportTemplate,
    TemplatePrompt,
    TransitionReport,
    TransitionTag,
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
# treated as skip-safe. ReportTag (TRWI-11) is a tag/source choice-field
# join row with no free text and no user FK at all, same category as
# PositionOverride. TransitionTag (2026-09 "Additional tags" autocomplete
# change) is the free-form tag vocabulary itself -- just a short ``name``
# string, same free-vocabulary category as jobs.Keyword/jobs.Major/
# users.Position, and never contains a person's name in practice (tags are
# theme words like "risk"/"continuity", not who said them).
register_skip(
    [
        PositionOverride,
        ReportTemplate,
        TemplatePrompt,
        ReportObligation,
        TransitionReport,
        ReportAcknowledgement,
        HandoffNotice,
        ReportTag,
        TransitionTag,
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
