import datetime
import logging
import time

from allauth.account.adapter import get_adapter
from allauth_2fa.middleware import BaseRequire2FAMiddleware
from dash.exceptions import CallbackException
from django.conf import settings
from django.contrib import messages
from django.db import connection, reset_queries
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
from django.utils.safestring import mark_safe

from core.models import current_month, current_term
from core.utils import check_nat_officer, check_officer
from thetatauCMT.forms.models import PledgeProgram, RiskManagement

perf_logger = logging.getLogger("perf")
dash_logger = logging.getLogger("django_plotly_dash.stale_callback")
logger = logging.getLogger(__name__)

NATOFF_2FA_CONFIG_KEY = "NATOFF_2FA_REQUIRED_FROM"


def natoff_2fa_required_from():
    """The date National Officers must use two-factor sign-in from, or None (Q27 A)."""
    from thetatauCMT.configs.models import Config

    raw = Config.get_value(NATOFF_2FA_CONFIG_KEY).strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except ValueError:
        logger.warning("%s is not a date (YYYY-MM-DD): %r", NATOFF_2FA_CONFIG_KEY, raw)
        return None


class Require2FAMiddleware(BaseRequire2FAMiddleware):
    """Two-factor sign-in for Admins, Chapter Support Specialists and National Officers.

    Admins and CSSs must set it up before anything else (Q19). National Officers must from
    the date in the ``NATOFF_2FA_REQUIRED_FROM`` Config setting; until then, without a
    device, they get a banner (``request.natoff_2fa_due``), and with the setting empty
    nothing changes for them (Q27 A). The ``natoff`` group is read raw, so hiding national
    officer functionality does not skip it. Everything is off while ``DEBUG`` is on.
    """

    def require_2fa(self, request):
        from thetatauCMT.support.services import css_state

        if settings.DEBUG:
            return False
        user = request.user
        if user.is_superuser or css_state(user).is_css:
            return True
        if not user.in_national_officer_group:
            return False
        due = natoff_2fa_required_from()
        if due is None:
            return False
        if timezone.localdate() >= due:
            return True
        if not get_adapter(request).has_2fa_enabled(user):
            request.natoff_2fa_due = due
        return False


class RMPSignMiddleware(MiddlewareMixin):
    """Django Middleware (add to MIDDLEWARE) to enforce members to sign rmp"""

    def __call__(self, request):
        response = self.get_response(request)
        # only relevant for logged in users
        if not request.user.is_authenticated:
            return response
        path = request.path
        # pages to not redirect on (no recursion please!)
        if path in settings.TERMS_EXCLUDE_URL_LIST:
            return response
        if request.user.requires_rmp and not RiskManagement.user_signed_this_semester(request.user):
            messages.add_message(
                request,
                messages.ERROR,
                "You must sign the Risk Management Policies and Agreements " "of Theta Tau this semester.",
            )
            return redirect("rmp")
        should_submit = (current_term() == "sp" and current_month() >= 2) or (
            current_term() == "fa" and current_month() >= 9
        )
        if request.user.chapter_officer(altered=False):
            if should_submit and not PledgeProgram.signed_this_semester(request.user.current_chapter):
                host = settings.CURRENT_URL
                link = reverse("viewflow:forms:pledgeprogramprocess:start")
                link = host + link
                messages.add_message(
                    request,
                    messages.ERROR,
                    mark_safe(
                        "Your chapter must submit the New Member Education Program this semester.<br>"
                        f"Please go to Forms --> New Member Education Program or click this <a href={link}>link</a>."
                    ),
                )
        elif getattr(request, "css_view_only", False):
            # A Chapter Support Specialist sees the same reminder, as information (S13). Only
            # page loads add it: the dashboard's callbacks are requests too, and each would
            # queue another copy for the next page.
            if (
                request.method == "GET"
                and response.status_code == 200
                and response.get("Content-Type", "").startswith("text/html")
                and should_submit
                and not PledgeProgram.signed_this_semester(request.user.current_chapter)
            ):
                messages.add_message(
                    request,
                    messages.INFO,
                    "This chapter has not submitted its New Member Education program this semester.",
                )
        return response


class OfficerMiddleware(MiddlewareMixin):
    """Django Middleware (add to MIDDLEWARE) to officer info to every page"""

    def process_request(self, request):
        if request.user.is_authenticated:
            check_nat_officer(request)
            check_officer(request)


class QueryTimingMiddleware:
    """Staging-only profiler: log per-request wall time + SQL stats and expose
    them as X-Perf-* response headers (visible in browser DevTools). Forces the
    debug cursor so query timings are captured even when DEBUG is False."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        connection.force_debug_cursor = True
        reset_queries()
        start = time.perf_counter()
        response = self.get_response(request)
        elapsed = time.perf_counter() - start
        queries = connection.queries
        sql_time = sum(float(query["time"]) for query in queries)
        response["X-Perf-Total"] = f"{elapsed:.3f}s"
        response["X-Perf-Queries"] = str(len(queries))
        response["X-Perf-SQL"] = f"{sql_time:.3f}s"
        perf_logger.warning(
            "PERF %s %s -> %.3fs total, %d queries, %.3fs SQL",
            request.method,
            request.path,
            elapsed,
            len(queries),
            sql_time,
        )
        return response


class PlotlyDashStaleCallbackMiddleware:
    """Return a clean 400 instead of a 500 for a stale django-plotly-dash callback.

    DjangoDash apps register their callback map once per worker process at
    import time, and production (PythonAnywhere) only picks up code changes
    on a manual reload. A browser tab left open across a reload/deploy (or
    still pointed at a retired dash app) posts an Input/Output shape the
    running process no longer recognizes, which dash raises as
    `CallbackException("Inputs do not match callback definition")`. That's a
    stale client, not a server bug, so it's handled here in `process_view`
    (before the exception ever propagates) instead of surfacing as an
    unhandled 500.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.path.startswith("/django_plotly_dash/"):
            return None
        try:
            return view_func(request, *view_args, **view_kwargs)
        except CallbackException as exc:
            dash_logger.warning("Stale django-plotly-dash callback on %s: %s", request.path, exc)
            return JsonResponse(
                {"error": "This dashboard was updated. Please refresh the page."},
                status=400,
            )
