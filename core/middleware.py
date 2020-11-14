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
        path = path.strip("/")
        if (
            path
            in "logout forms/rmp rmp electronic_terms forms/pledgeprogram forms/report forms/report".split()
        ) or settings.DEBUG:
            return response
        if request.user.is_officer:
            if not RiskManagement.user_signed_this_year(request.user):
                messages.add_message(
                    request,
                    messages.ERROR,
                    f"You must sign the Risk Management Policies and Agreements "
                    f"of Theta Tau this year.",
                )
                return redirect("rmp")
        if request.user.chapter_officer(altered=False):
            if not PledgeProgram.signed_this_semester(request.user.current_chapter):
                messages.add_message(
                    request,
                    messages.ERROR,
                    f"Your chapter must submit the New Member Education Program this semester.",
                )
                return redirect("forms:pledge_program")
            if not ChapterReport.signed_this_semester(request.user.current_chapter):
                messages.add_message(
                    request,
                    messages.ERROR,
                    f"Your chapter must submit the Chapter Report this semester.",
                )
                return redirect("forms:report")
        return response


class OfficerMiddleware(MiddlewareMixin):
    """Django Middleware (add to MIDDLEWARE) to officer info to every page"""

    def process_request(self, request):
        if request.user.is_authenticated:
            check_nat_officer(request)
            check_officer(request)
