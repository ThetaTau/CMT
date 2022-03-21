from dj_anonymizer.register_models import register_skip

from events.models import Event, Picture

register_skip([Event, Picture])
