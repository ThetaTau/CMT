from dj_anonymizer.register_models import register_skip

from jobs.models import Job, JobSearch, Keyword, Major

register_skip([Job, JobSearch, Keyword, Major])
