from dj_anonymizer.register_models import AnonymBase, register_clean

from thetatauCMT.notes.models import ChapterNote, UserNote

register_clean(
    [
        (UserNote, AnonymBase),
        (ChapterNote, AnonymBase),
    ]
)
