from dj_anonymizer.register_models import AnonymBase, register_clean, register_skip

from thetatauCMT.competitions.models import (
    Assignment,
    Competition,
    CriterionScore,
    Entry,
    EntryFile,
    EntryMember,
    Judge,
    KeyDate,
    NotificationLog,
    Participant,
    Round,
    RubricCriterion,
    Scorecard,
    SubmissionItem,
)

# The setup (the competition, its key dates, rounds, rubrics and the items each round
# collects) is national content with no personal data, and a judge row only points at a
# member through a foreign key (anonymized via the User model).
register_skip([Competition, KeyDate, Round, RubricCriterion, SubmissionItem, Judge])

# Everything chapters and judges write or upload is free text or files that can name people:
# the chapter's note, entries (titles, summaries, manager notes), team roles, the uploaded
# files, judges' feedback, comments and private notes, plus the email log's recipient
# addresses. Drop every row; the competition's demo seed command rebuilds QA data.
register_clean(
    [
        (Participant, AnonymBase),
        (Entry, AnonymBase),
        (EntryMember, AnonymBase),
        (EntryFile, AnonymBase),
        (Assignment, AnonymBase),
        (Scorecard, AnonymBase),
        (CriterionScore, AnonymBase),
        (NotificationLog, AnonymBase),
    ]
)
