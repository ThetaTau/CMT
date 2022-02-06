from dj_anonymizer.register_models import AnonymBase, register_anonym
from dj_anonymizer import anonym_field
from faker import Factory

from surveys.models import DepledgeSurvey

fake = Factory.create()


class DepledgeSurveyAnonym(AnonymBase):
    reason_other = anonym_field.function(fake.sentence)
    decided_other = anonym_field.function(fake.sentence)
    enjoyed = anonym_field.function(fake.paragraph)
    improve = anonym_field.function(fake.paragraph)
    extra_notes = anonym_field.function(fake.paragraph)

    class Meta:
        exclude_fields = ["user", "created", "modified", "reason", "decided", "contact"]


register_anonym(
    [
        (DepledgeSurvey, DepledgeSurveyAnonym),
    ]
)
