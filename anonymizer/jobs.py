from dj_anonymizer import fields
from dj_anonymizer.register_models import AnonymBase, register_anonym, register_skip
from faker import Factory

from thetatauCMT.jobs.models import Job, JobPostingBan, JobSearch, Keyword, Major

fake = Factory.create()

register_skip([Job, JobSearch, Keyword, Major])


class JobPostingBanAnonym(AnonymBase):
    reason = fields.function(fake.sentence)

    class Meta:
        exclude_fields = [
            "banned_at",
            "created",
            "modified",
        ]


register_anonym(
    [
        (JobPostingBan, JobPostingBanAnonym),
    ]
)
