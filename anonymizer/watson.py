from dj_anonymizer.register_models import AnonymBase, register_clean
from watson.models import SearchEntry

register_clean(
    [
        (SearchEntry, AnonymBase),
    ]
)
