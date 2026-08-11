"""Template context for the outstanding-ballot nudge.

This runs on every rendered page, so anyone who holds no role -- the large
majority of members -- is disqualified before a query happens.
"""

from .models import Ballot


def outstanding_ballots(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated or not user.current_roles:
        return {}
    ballots = list(Ballot.outstanding_for_user(user))
    if not ballots:
        return {}
    return {
        "outstanding_ballots": ballots,
        "outstanding_ballot_count": len(ballots),
    }
