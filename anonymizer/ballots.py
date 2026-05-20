from dj_anonymizer.register_models import AnonymBase, register_clean

from thetatauCMT.ballots.models import Ballot, BallotComplete

# Just clean for now, not really using ballots
register_clean(
    [
        (Ballot, AnonymBase),
        (BallotComplete, AnonymBase),
    ]
)
