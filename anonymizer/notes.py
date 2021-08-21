from dj_anonymizer.register_models import register_clean

from notes.models import UserNote, ChapterNote

register_clean([UserNote, ChapterNote])
