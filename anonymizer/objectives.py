from dj_anonymizer.register_models import register_clean, AnonymBase

from objectives.models import Objective, Action

register_clean(
    [
        (Objective, AnonymBase),
        (Action, AnonymBase),
    ]
)
