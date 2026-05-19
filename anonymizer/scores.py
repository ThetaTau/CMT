from dj_anonymizer.register_models import register_skip

from thetatauCMT.scores.models import ScoreChapter, ScoreType

register_skip([ScoreType, ScoreChapter])
