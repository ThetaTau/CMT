from dj_anonymizer.register_models import register_skip

from chapters.models import Chapter, ChapterCurricula

register_skip([Chapter, ChapterCurricula])
