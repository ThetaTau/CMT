"""Unit tests for core/utils.py retry helpers.

Covers ``retry_google_api`` and ``_google_error_status`` — the transient-error
retry wrapper introduced to stop Google Cloud Storage 429s (issue #957) and
Google Drive 5xx exports (issue #944) from surfacing as user-facing 500s.
"""

from unittest.mock import patch

import pytest

from core.utils import _google_error_status, retry_google_api

# ---------------------------------------------------------------------------
# Fake exception shapes matching the real Google client libraries
# ---------------------------------------------------------------------------


class _ApiCoreError(Exception):
    """Mimics google.api_core.exceptions.* (Cloud Storage): int ``.code``."""

    def __init__(self, code):
        super().__init__(f"status {code}")
        self.code = code


class _DriveApiError(Exception):
    """Mimics pydrive2.files.ApiRequestError: ``.error`` dict with ``code``."""

    def __init__(self, code):
        super().__init__(f"status {code}")
        self.error = {"code": code, "errors": [{"reason": "internalError"}]}


class _Resp:
    def __init__(self, status):
        self.status = status


class _HttpError(Exception):
    """Mimics googleapiclient.errors.HttpError: ``.resp.status``."""

    def __init__(self, status):
        super().__init__(f"status {status}")
        self.resp = _Resp(status)


# ---------------------------------------------------------------------------
# _google_error_status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc, expected",
    [
        (_ApiCoreError(429), 429),
        (_ApiCoreError(500), 500),
        (_DriveApiError(500), 500),
        (_DriveApiError(429), 429),
        (_HttpError(503), 503),
        (ValueError("no status here"), None),
    ],
)
def test_google_error_status_extracts_code(exc, expected):
    assert _google_error_status(exc) == expected


def test_google_error_status_handles_non_int_code():
    err = _DriveApiError("not-a-number")
    assert _google_error_status(err) is None


# ---------------------------------------------------------------------------
# retry_google_api
# ---------------------------------------------------------------------------


def test_retry_returns_result_without_retrying_on_success():
    calls = []

    def op():
        calls.append(1)
        return "done"

    with patch("core.utils.time.sleep") as sleep:
        assert retry_google_api(op) == "done"
    assert len(calls) == 1
    sleep.assert_not_called()


def test_retry_recovers_after_transient_error():
    attempts = {"n": 0}

    def op():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _ApiCoreError(429)
        return "ok"

    with patch("core.utils.time.sleep") as sleep:
        assert retry_google_api(op, attempts=3) == "ok"
    assert attempts["n"] == 3
    # Slept between the two failures (2 retries -> 2 sleeps).
    assert sleep.call_count == 2


def test_retry_reraises_after_exhausting_attempts():
    def op():
        raise _DriveApiError(500)

    with patch("core.utils.time.sleep"):
        with pytest.raises(_DriveApiError):
            retry_google_api(op, attempts=3)


def test_retry_does_not_retry_non_transient_error():
    attempts = {"n": 0}

    def op():
        attempts["n"] += 1
        raise _HttpError(404)  # client error, not transient

    with patch("core.utils.time.sleep") as sleep:
        with pytest.raises(_HttpError):
            retry_google_api(op)
    assert attempts["n"] == 1  # failed fast, no retry
    sleep.assert_not_called()


def test_retry_does_not_retry_plain_exception():
    def op():
        raise ValueError("boom")

    with patch("core.utils.time.sleep") as sleep:
        with pytest.raises(ValueError):
            retry_google_api(op)
    sleep.assert_not_called()
