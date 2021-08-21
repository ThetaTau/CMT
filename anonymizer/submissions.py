from dj_anonymizer.register_models import AnonymBase, register_anonym
from dj_anonymizer import anonym_field
from faker import Factory

from submissions.models import Submission

fake = Factory.create()


class SubmissionAnonym(AnonymBase):
    file = anonym_field.function(fake.file_path)
    name = anonym_field.function(fake.sentence)
    slug = anonym_field.function(fake.slug)

    class Meta:
        exclude_fields = ["created", "modified", "task", "date", "score"]


register_anonym(
    [
        (Submission, SubmissionAnonym),
    ]
)
