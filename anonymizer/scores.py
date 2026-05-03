from dj_anonymizer.register_models import register_skip

from thetatauCMT.scores.models import ScoreType, ScoreChapter

register_skip([ScoreType, ScoreChapter])
