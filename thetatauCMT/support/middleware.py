import html
import re
from urllib.parse import urljoin, urlsplit

from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import Resolver404, resolve
from django.utils.http import url_has_allowed_host_and_scheme

from .services import VIEW_ONLY_MESSAGE, is_personal_action

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Added to every form a CSS may not submit; base.html disables their submit buttons (S14).
LOCKED_FORM_ATTRIBUTE = "data-css-view-only"
_FORM_TAG = re.compile(r"<form\b[^>]*>", re.IGNORECASE)
_POST_METHOD = re.compile(r"""(?<![\w-])method\s*=\s*["']?post\b""", re.IGNORECASE)
_ACTION = re.compile(r"""(?<![\w-])action\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""", re.IGNORECASE)


class ViewOnlyCSSMiddleware:
    """Refuse changes from a Chapter Support Specialist viewing an assigned chapter (Q1).

    ``core.middleware.OfficerMiddleware`` sets ``request.css_view_only``. Submissions that
    only touch the CSS's own account (``services.PERSONAL_ACTIONS``, Q22) still go through.
    A few pages change data on a plain page load; those check ``request.css_view_only``
    themselves (see ``UserListView.get``). On the way out, every form on the page that a
    CSS could not submit is marked, so its buttons can be shown disabled (S14).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(request, "css_view_only", False):
            mark_locked_forms(request, response)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not getattr(request, "css_view_only", False) or request.method in SAFE_METHODS:
            return None
        if is_personal_action(request.resolver_match):
            return None
        return refuse(request)


def refuse(request):
    """The response for a CSS who tried to change something."""
    if _wants_json(request):
        return JsonResponse({"error": VIEW_ONLY_MESSAGE}, status=403)
    messages.error(request, VIEW_ONLY_MESSAGE)
    return HttpResponseRedirect(_back_url(request))


def mark_locked_forms(request, response):
    """Add ``LOCKED_FORM_ATTRIBUTE`` to each form that posts to a page refusing a CSS."""
    if response.streaming or response.status_code != 200:
        return
    if not response.get("Content-Type", "").startswith("text/html"):
        return
    content = response.content.decode(response.charset)
    marked = _FORM_TAG.sub(lambda match: _mark(match.group(0), request), content)
    if marked != content:
        response.content = marked.encode(response.charset)
        if response.has_header("Content-Length"):
            response["Content-Length"] = str(len(response.content))


def _mark(tag, request):
    if LOCKED_FORM_ATTRIBUTE in tag or not _is_locked(tag, request):
        return tag
    return f"{tag[:5]} {LOCKED_FORM_ATTRIBUTE}{tag[5:]}"


def _is_locked(tag, request):
    if not _POST_METHOD.search(tag):
        return False
    found = _ACTION.search(tag)
    action = html.unescape(next(value for value in found.groups() if value is not None)) if found else ""
    target = urlsplit(urljoin(request.path, action))
    if target.netloc and target.netloc != request.get_host():
        return False
    try:
        match = resolve(target.path or request.path)
    except Resolver404:
        return False
    return not is_personal_action(match)
    if _wants_json(request):
        return JsonResponse({"error": VIEW_ONLY_MESSAGE}, status=403)
    messages.error(request, VIEW_ONLY_MESSAGE)
    return HttpResponseRedirect(_back_url(request))


def _wants_json(request):
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return True
    return "application/json" in request.headers.get("accept", "") or request.content_type == "application/json"


def _back_url(request):
    referer = request.META.get("HTTP_REFERER", "")
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return referer
    return request.get_full_path()
