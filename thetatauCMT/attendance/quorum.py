"""Configurable quorum calculation for the attendance module.

The rule is configurable via ``settings.ATTENDANCE_QUORUM_RULE`` (default a
simple majority). This keeps the quorum policy out of hard-coded logic.
"""

import math

from django.conf import settings


def compute_quorum(active_count):
    """Number of active members required for quorum given ``active_count``.

    Rules (``settings.ATTENDANCE_QUORUM_RULE``):
    - ``"majority"`` (default): ``floor(active_count / 2) + 1``
    - ``"two_thirds"``: ``ceil(active_count * 2 / 3)``
    - a float ``0 < x <= 1``: ``ceil(active_count * x)``
    """
    if not active_count or active_count < 0:
        return 0
    rule = getattr(settings, "ATTENDANCE_QUORUM_RULE", "majority")
    if rule == "two_thirds":
        return math.ceil(active_count * 2 / 3)
    fraction = None
    if not isinstance(rule, str):
        try:
            fraction = float(rule)
        except (TypeError, ValueError):
            fraction = None
    else:
        try:
            fraction = float(rule)
        except ValueError:
            fraction = None
    if fraction is not None and 0 < fraction <= 1:
        return math.ceil(active_count * fraction)
    # Default: simple majority.
    return active_count // 2 + 1


def quorum_status(active_count, attended_active_count):
    """Snapshot dict describing quorum met/not-met with counts."""
    required = compute_quorum(active_count)
    return {
        "active_count": active_count,
        "attended_active": attended_active_count,
        "required": required,
        "met": active_count > 0 and attended_active_count >= required,
    }
