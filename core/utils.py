import logging
import time

from django.conf import settings
from pydrive2.auth import GoogleAuth

logger = logging.getLogger(__name__)

# HTTP statuses returned by Google Cloud Storage / Google Drive for requests
# that succeed when retried: 429 (rate limit for object mutation operations) and
# the transient 5xx "Internal Error" family.
_TRANSIENT_GOOGLE_STATUSES = frozenset({429, 500, 502, 503, 504})


def _google_error_status(exc):
    """Best-effort extraction of an HTTP status code from a Google API error.

    Google's client libraries surface the status differently depending on which
    API raised it:

    * ``google.api_core.exceptions`` (Cloud Storage) expose an int ``.code``.
    * ``pydrive2.files.ApiRequestError`` exposes an ``.error`` dict with ``code``.
    * ``googleapiclient.errors.HttpError`` exposes ``.resp.status``.
    * ``requests``-style responses expose ``.status_code``.

    Returns the status as an ``int`` when it can be determined, otherwise
    ``None``.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, int):
        return code
    error = getattr(exc, "error", None)
    if isinstance(error, dict):
        try:
            return int(error.get("code"))
        except (TypeError, ValueError):
            pass
    status = getattr(getattr(exc, "resp", None), "status", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    try:
        return int(status)
    except (TypeError, ValueError):
        return None


def retry_google_api(
    operation,
    *,
    attempts=3,
    initial_delay=1.0,
    backoff=2.0,
    description="Google API operation",
):
    """Run ``operation`` retrying transient Google API failures with backoff.

    Google Cloud Storage returns HTTP 429 when the same object is mutated more
    than once per second, and Google Drive intermittently returns HTTP 5xx
    "Internal Error" for exports that succeed on a retry. Both are transient, so
    retry with exponential backoff rather than surfacing a 500 to the user.

    :param operation: a zero-argument callable that performs the request.
    :param attempts: total number of tries before giving up.
    :param initial_delay: seconds to wait before the first retry.
    :param backoff: multiplier applied to the delay after each failed attempt.
    :param description: human-readable label used in the retry log message.
    :returns: whatever ``operation`` returns.
    :raises: the last exception when every attempt fails or the error is not a
        recognised transient status.
    """
    delay = initial_delay
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            status = _google_error_status(exc)
            if status not in _TRANSIENT_GOOGLE_STATUSES or attempt == attempts:
                raise
            logger.warning(
                "%s failed with transient status %s (attempt %s/%s); retrying in %.1fs",
                description,
                status,
                attempt,
                attempts,
                delay,
            )
            time.sleep(delay)
            delay *= backoff


def check_officer(request):
    user = request.user
    if getattr(user, "natoff_hidden", False):
        # National Officer previewing the site as a member: officer status now
        # comes only from an actual chapter role (including the UserAlter role),
        # never from ``natoff`` / ``officer`` group membership.
        if user.chapter_officer():
            request.is_officer = True
        return request
    if user.groups.filter(name__in=["officer", "natoff"]).exists():
        request.is_officer = True
    return request


def check_nat_officer(request):
    user = request.user
    if user.groups.filter(name="natoff").exists():
        # Raw group membership — always set so the "view as member" switch-back
        # controls stay available even while natoff functionality is hidden.
        request.in_natoff_group = True
        if not getattr(user, "natoff_hidden", False):
            request.is_nat_officer = True
    return request


def login_with_service_account():
    """
    Google Drive service with a service account.
    note: for the service account to work, you need to share the folder or
    files with the service account email.

    :return: google auth
    """
    # Define the settings dict to use a service account
    # We also can use all options available for the settings dict like
    # oauth_scope,save_credentials,etc.
    config = {
        "client_config_backend": "service",
        "service_config": {
            "client_json_file_path": str(settings.ROOT_DIR / "secrets" / "ChapterManagementTool-b239bceff1a7.json"),
        },
    }
    # Create instance of GoogleAuth
    gauth = GoogleAuth(settings=config)
    # Authenticate
    gauth.ServiceAuth()
    return gauth
