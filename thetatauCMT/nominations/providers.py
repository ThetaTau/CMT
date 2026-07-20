"""Pluggable training-completion providers (VWI-7).

A thin seam so a future LMS / Vector API or webhook can mark a nominee's
required trainings complete without changing the flow. The default
``ManualTrainingProvider`` records completion directly on the ``Nomination``.
"""

from django.conf import settings
from django.utils.module_loading import import_string

TRAINING_CMT = "cmt_lms"
TRAINING_VECTOR = "vector"

TRAININGS = [
    (TRAINING_CMT, "CMT LMS Volunteer Training"),
    (TRAINING_VECTOR, "Vector CommunityEdu H&S Training"),
]
TRAINING_LABELS = dict(TRAININGS)
REQUIRED_TRAINING_KEYS = [TRAINING_CMT, TRAINING_VECTOR]

_FIELD_BY_KEY = {
    TRAINING_CMT: "training_cmt_complete",
    TRAINING_VECTOR: "training_vector_complete",
}


class TrainingCompletionProvider:
    """Interface for marking / checking a nominee's training completion.

    Subclass and override ``mark_complete`` / ``is_complete`` to integrate an
    LMS or webhook; point ``settings.NOMINATION_TRAINING_PROVIDER`` at the
    dotted path. The flow and views are unchanged.
    """

    def mark_complete(self, nomination, training_key, completed_by=None):
        raise NotImplementedError

    def is_complete(self, nomination, training_key):
        raise NotImplementedError

    def all_required_complete(self, nomination):
        return all(self.is_complete(nomination, key) for key in REQUIRED_TRAINING_KEYS)


class ManualTrainingProvider(TrainingCompletionProvider):
    """Default provider: completion is recorded manually on the Nomination."""

    def _field(self, training_key):
        field = _FIELD_BY_KEY.get(training_key)
        if field is None:
            raise ValueError(f"Unknown training key: {training_key}")
        return field

    def mark_complete(self, nomination, training_key, completed_by=None):
        field = self._field(training_key)
        setattr(nomination, field, True)
        nomination.save(update_fields=[field])

    def is_complete(self, nomination, training_key):
        return bool(getattr(nomination, self._field(training_key)))


def get_training_provider():
    """Return the configured provider (default: :class:`ManualTrainingProvider`)."""
    path = getattr(settings, "NOMINATION_TRAINING_PROVIDER", None)
    if path:
        return import_string(path)()
    return ManualTrainingProvider()
