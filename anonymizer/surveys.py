from dj_anonymizer.register_models import AnonymBase, register_anonym, register_skip
from dj_anonymizer import anonym_field
from faker import Factory

from surveys.models import DepledgeSurvey, Survey
from survey.models import Category, Response, Answer, Question
from surveys.models import Survey as Survey_base

register_skip([Category, Survey, Survey_base, Question, Response])

fake = Factory.create()


class DepledgeSurveyAnonym(AnonymBase):
    reason_other = anonym_field.function(fake.sentence)
    decided_other = anonym_field.function(fake.sentence)
    enjoyed = anonym_field.function(fake.paragraph)
    improve = anonym_field.function(fake.paragraph)
    extra_notes = anonym_field.function(fake.paragraph)

    class Meta:
        exclude_fields = ["user", "created", "modified", "reason", "decided", "contact"]


class AnswerAnonym(AnonymBase):
    body = anonym_field.function(fake.sentence)

    class Meta:
        exclude_fields = ["response", "question", "created", "updated"]


register_anonym([(DepledgeSurvey, DepledgeSurveyAnonym), (Answer, AnswerAnonym)])
