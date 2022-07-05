from dj_anonymizer.register_models import register_clean

from objectives.models import Objective, Action

register_clean([Objective, Action])
