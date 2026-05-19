from dj_anonymizer.register_models import AnonymBase, register_clean

from thetatauCMT.objectives.models import Action, Objective

register_clean(
    [
        (Objective, AnonymBase),
        (Action, AnonymBase),
    ]
)
