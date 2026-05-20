from dj_anonymizer.register_models import AnonymBase, register_clean

from thetatauCMT.finances.models import Invoice

register_clean(
    [
        (Invoice, AnonymBase),
    ]
)
