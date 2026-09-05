from dj_anonymizer.register_models import register_skip

from thetatauCMT.transitions.models import PositionOverride, ReportObligation, ReportTemplate, TemplatePrompt

# PositionOverride/ReportTemplate/TemplatePrompt are admin-managed config and
# prompt-set content (TRWI-1/2), seeded via management commands -- no
# personal data. ReportObligation (TRWI-3) references a person only through
# the officer/role_change foreign keys (anonymized via the User model) and
# holds no raw identity fields of its own (dates, position keys, status).
register_skip(
    [
        PositionOverride,
        ReportTemplate,
        TemplatePrompt,
        ReportObligation,
    ]
)
