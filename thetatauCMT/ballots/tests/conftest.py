import contextlib
from datetime import timedelta
from unittest import mock

import pytest


@pytest.fixture
def freeze_close():
    """Pin ``timezone.now`` either side of a ballot's 5pm Pacific close."""

    @contextlib.contextmanager
    def _freeze(ballot, minutes_before=0, minutes_after=0):
        moment = ballot.closes_at - timedelta(minutes=minutes_before) + timedelta(minutes=minutes_after)
        with mock.patch("django.utils.timezone.now", return_value=moment):
            yield moment

    return _freeze
