"""Shared test helpers for the awards app.

Module name starts with ``_`` so pytest does not collect it as a test module.
"""


def sign_rmp(user):
    """Give ``user`` a current Risk Management signature.

    ``RMPSignMiddleware`` redirects any authenticated user who has not signed the
    Risk Management Policy this semester, so award view tests must sign one. The
    signature is dated to the start of the current semester window to avoid
    term-boundary flakiness.
    """
    from core.models import semester_encompass_start_end_date
    from thetatauCMT.forms.tests.factories import RiskManagementFactory

    start, _end = semester_encompass_start_end_date()
    if hasattr(start, "date"):
        start = start.date()
    RiskManagementFactory.create(user=user, date=start)
