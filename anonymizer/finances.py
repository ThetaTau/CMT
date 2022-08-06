from dj_anonymizer.register_models import register_clean, AnonymBase

from finances.models import Invoice

register_clean(
    [
        (Invoice, AnonymBase),
    ]
)
