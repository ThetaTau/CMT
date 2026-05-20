from dj_anonymizer import fields
from dj_anonymizer.register_models import AnonymBase, register_anonym, register_skip
from faker import Factory
from survey.models import Answer, Category, Question, Response
from survey.models import Survey as Survey_base

from thetatauCMT.surveys.models import DepledgeSurvey, Survey

register_skip([Category, Survey, Survey_base, Question, Response])

fake = Factory.create()


class DepledgeSurveyAnonym(AnonymBase):
    reason_other = fields.function(fake.sentence)
    decided_other = fields.function(fake.sentence)
    enjoyed = fields.function(fake.paragraph)
    improve = fields.function(fake.paragraph)
    extra_notes = fields.function(fake.paragraph)

    class Meta:
        exclude_fields = ["user", "created", "modified", "reason", "decided", "contact"]


class AnswerAnonym(AnonymBase):
    body = fields.function(fake.sentence)

    class Meta:
        exclude_fields = ["response", "question", "created", "updated"]


register_anonym([(DepledgeSurvey, DepledgeSurveyAnonym), (Answer, AnswerAnonym)])
