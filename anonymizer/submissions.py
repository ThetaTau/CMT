from dj_anonymizer.register_models import AnonymBase, register_anonym
from dj_anonymizer import anonym_field
from faker import Factory

from submissions.models import Submission, Picture, GearArticle

fake = Factory.create()


class SubmissionAnonym(AnonymBase):
    file = anonym_field.function(fake.file_path)
    name = anonym_field.function(fake.sentence)
    slug = anonym_field.function(fake.slug)

    class Meta:
        exclude_fields = ["created", "modified", "task", "date", "score"]


class PictureAnonym(AnonymBase):
    image = anonym_field.function(fake.file_path)
    description = anonym_field.function(fake.sentence)

    class Meta:
        exclude_fields = ["created", "modified", "submission"]


class GearArticleAnonym(AnonymBase):
    article = anonym_field.function(fake.paragraph)
    notes = anonym_field.function(fake.sentence)

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
