from dj_anonymizer.register_models import register_clean

from finances.models import Transaction

register_clean([Transaction])
