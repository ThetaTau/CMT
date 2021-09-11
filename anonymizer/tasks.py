from dj_anonymizer.register_models import register_skip

from tasks.models import Task, TaskDate, TaskChapter

register_skip([Task, TaskDate, TaskChapter])
