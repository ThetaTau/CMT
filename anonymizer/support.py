from dj_anonymizer.register_models import AnonymBase, register_clean

from thetatauCMT.support.models import ChapterSupportAssignment, SupportDigestEntry

# Assignment notes are free text a manager writes about a person, and digest entries keep
# rendered chapter emails full of member names and addresses. Role changes
# (users.UserRoleChange) are already dropped from anonymized copies, and an assignment means
# nothing without the CSS role, so drop both tables; the seed_css_demo command (CSSWI-9)
# rebuilds demo data.
register_clean(
    [
        (ChapterSupportAssignment, AnonymBase),
        (SupportDigestEntry, AnonymBase),
    ]
)
