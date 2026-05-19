from dj_anonymizer.register_models import register_skip

from thetatauCMT.tasks.models import Task, TaskChapter, TaskDate

register_skip([Task, TaskDate, TaskChapter])
