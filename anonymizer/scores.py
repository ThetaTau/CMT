from dj_anonymizer.register_models import register_skip

from scores.models import ScoreType, ScoreChapter

register_skip([ScoreType, ScoreChapter])
