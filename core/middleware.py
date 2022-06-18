from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from allauth_2fa.middleware import BaseRequire2FAMiddleware

from forms.models import RiskManagement, PledgeProgram, ChapterReport
from core.utils import check_officer, check_nat_officer


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
                "You must sign the Risk Management Policies and Agreements "
                "of Theta Tau this semester.",
            )
            return redirect("rmp")
        if request.user.chapter_officer(altered=False):
            if not PledgeProgram.signed_this_semester(request.user.current_chapter):
                messages.add_message(
                    request,
                    messages.ERROR,
                    "Your chapter must submit the New Member Education Program this semester. "
                    "Please go to Forms --> New Member Education Program",
                )
        return response


class OfficerMiddleware(MiddlewareMixin):
    """Django Middleware (add to MIDDLEWARE) to officer info to every page"""

    def process_request(self, request):
        if request.user.is_authenticated:
            check_nat_officer(request)
            check_officer(request)
