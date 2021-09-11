from dj_anonymizer.register_models import register_clean

from finances.models import Invoice

register_clean([Invoice])
