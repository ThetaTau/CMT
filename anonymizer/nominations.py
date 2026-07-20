from dj_anonymizer.register_models import register_skip

from thetatauCMT.nominations.models import Nomination, NominationContact

# The volunteer nomination workflow is a viewflow Process. Like the other
# workflow Process models in this project (InitiationProcess, PledgeProcess,
# ReturnStudent, ...), it is left as-is on the anonymized staging database.
register_skip(
    [
        Nomination,
        NominationContact,
    ]
)
