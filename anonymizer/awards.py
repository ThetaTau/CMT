from dj_anonymizer.register_models import AnonymBase, register_clean, register_skip

from thetatauCMT.awards.models import (
    AwardCycle,
    AwardDigestRun,
    AwardGrant,
    AwardImportMatchQueueItem,
    AwardNominationProcess,
    AwardType,
    EligibilityRule,
    GrantArtifact,
    GrantAudit,
    OfficerBadge,
)

# AwardType, AwardCycle and EligibilityRule are admin-managed catalog /
# configuration. AwardGrant and GrantAudit record public, retained award
# history and reference members / chapters / regions only through foreign keys
# (anonymized via those models). AwardNominationProcess is a viewflow Process
# (like the volunteer Nomination) and is left as-is. So all are skipped on the
# anonymized staging database.
register_skip(
    [
        AwardType,
        AwardCycle,
        AwardGrant,
        GrantAudit,
        EligibilityRule,
        AwardNominationProcess,
        GrantArtifact,
        AwardDigestRun,
        OfficerBadge,
    ]
)

# AwardImportMatchQueueItem stores raw, as-uploaded identity fields (member
# names / emails, the full original CSV row) for legacy-award matching -- real
# personal data in a transient processing queue, so drop every row (mirrors the
# attendance MatchQueueItem).
register_clean(
    [
        (AwardImportMatchQueueItem, AnonymBase),
    ]
)
