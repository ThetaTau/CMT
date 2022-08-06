from dj_anonymizer.register_models import register_clean, AnonymBase

from watson.models import SearchEntry

register_clean(
    [
        (SearchEntry, AnonymBase),
    ]
)
