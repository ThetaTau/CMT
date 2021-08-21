from dj_anonymizer.register_models import register_skip

from viewflow.models import Process, Task

register_skip([Process, Task])
