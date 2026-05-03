from dj_anonymizer.register_models import register_clean, AnonymBase

from thetatauCMT.notes.models import UserNote, ChapterNote

register_clean(
    [
        (UserNote, AnonymBase),
        (ChapterNote, AnonymBase),
    ]
)
