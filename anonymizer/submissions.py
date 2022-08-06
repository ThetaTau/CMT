from dj_anonymizer.register_models import AnonymBase, register_anonym
from dj_anonymizer import fields
from faker import Factory

from submissions.models import Submission, Picture, GearArticle

fake = Factory.create()


class SubmissionAnonym(AnonymBase):
    file = fields.function(fake.file_path)
    name = fields.function(fake.sentence)
    slug = fields.function(fake.slug)

    class Meta:
        exclude_fields = ["created", "modified", "task", "date", "score"]


class PictureAnonym(AnonymBase):
    image = fields.function(fake.file_path)
    description = fields.function(fake.sentence)

    class Meta:
        exclude_fields = ["created", "modified", "submission"]


class GearArticleAnonym(AnonymBase):
    article = fields.function(fake.paragraph)
    notes = fields.function(fake.sentence)

    class Meta:
        exclude_fields = [
            "created",
            "modified",
            "authors",
            "submission",
            "reviewed",
        ]


register_anonym(
    [
        (Submission, SubmissionAnonym),
        (Picture, PictureAnonym),
        (GearArticle, GearArticleAnonym),
    ]
)
