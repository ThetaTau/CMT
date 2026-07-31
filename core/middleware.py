import logging
import time

from allauth_2fa.middleware import BaseRequire2FAMiddleware
from django.conf import settings
from django.contrib import messages
from django.db import connection, reset_queries
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils.safestring import mark_safe

from core.models import current_month, current_term
from core.utils import check_nat_officer, check_officer
from thetatauCMT.forms.models import PledgeProgram, RiskManagement

perf_logger = logging.getLogger("perf")


class RequireSuperuser2FAMiddleware(BaseRequire2FAMiddleware):
    def require_2fa(self, request):
        # Superusers are require to have 2FA.
        if settings.DEBUG:
            return False
        return request.user.is_superuser


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
        if not RiskManagement.user_signed_this_semester(request.user):
            messages.add_message(
                request,
                messages.ERROR,
                "You must sign the Risk Management Policies and Agreements " "of Theta Tau this semester.",
            )
            return redirect("rmp")
        if request.user.chapter_officer(altered=False):
            should_submit = (current_term() == "sp" and current_month() >= 2) or (
                current_term() == "fa" and current_month() >= 9
            )
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
